from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root123@localhost/train_reservation'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(512))
    reservations = db.relationship('Reservation', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Train(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    train_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    source = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    departure_time = db.Column(db.Time, nullable=False)
    arrival_time = db.Column(db.Time, nullable=False)
    total_seats = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    train_id = db.Column(db.Integer, db.ForeignKey('train.id'), nullable=False)
    booking_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    travel_date = db.Column(db.Date, nullable=False)
    num_seats = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='confirmed')
    payment_status = db.Column(db.String(20), nullable=False, default='pending')
    train = db.relationship('Train', backref='reservations')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/search', methods=['POST'])
def search():
    source = request.form.get('source')
    destination = request.form.get('destination')
    date = request.form.get('date')
    trains = Train.query.filter_by(source=source, destination=destination).all()
    return render_template('search_results.html', trains=trains, date=date)

@app.route('/book/<int:train_id>', methods=['GET', 'POST'])
@login_required
def book(train_id):
    train = Train.query.get_or_404(train_id)
    if request.method == 'POST':
        num_seats = int(request.form.get('num_seats'))
        travel_date = datetime.strptime(request.form.get('travel_date'), '%Y-%m-%d').date()
        
        if num_seats <= train.available_seats:
            total_price = num_seats * train.price
            reservation = Reservation(
                user_id=current_user.id,
                train_id=train_id,
                travel_date=travel_date,
                num_seats=num_seats,
                total_price=total_price
            )
            train.available_seats -= num_seats
            db.session.add(reservation)
            db.session.commit()
            return redirect(url_for('pay', reservation_id=reservation.id))
        else:
            flash('Not enough seats available!', 'danger')
    
    return render_template('book.html', train=train)

@app.route('/my_bookings')
@login_required
def my_bookings():
    reservations = Reservation.query.filter_by(user_id=current_user.id).all()
    return render_template('my_bookings.html', reservations=reservations)

@app.route('/pay/<int:reservation_id>', methods=['GET', 'POST'])
@login_required
def pay(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    if reservation.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        reservation.payment_status = 'paid'
        db.session.commit()
        flash('Payment successful! Your ticket is booked.', 'success')
        return redirect(url_for('my_bookings'))
    return render_template('payment.html', reservation=reservation)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 