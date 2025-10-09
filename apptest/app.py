from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from datetime import datetime
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads/'

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///solar.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

def get_weather(latitude, longitude):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True
    }

    response = requests.get(url, params=params)
    data = response.json()

    current = data.get("current_weather", {})
    temperature = current.get("temperature")
    weather_code = current.get("weathercode")

    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }

    condition = weather_codes.get(weather_code, "Unknown")

    return temperature, condition

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    file = db.Column(db.String(200), default='default.png')

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ""
    if request.method == 'POST':
        name = request.form.get('regName')
        email = request.form.get('regEmail')
        password = request.form.get('regPassword')
        confpassword = request.form.get('confPassword')
        if password != confpassword:
            msg = "Passwords must match"
            return render_template('register.html', msg = msg)
        if not name or not email or not password:
            msg = "Please fill all fields"
            return render_template('register.html', msg = msg)
        if User.query.filter_by(email=email).first():
            msg = "Email already exists"
            return render_template('register.html', msg = msg)
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(name=name, email=email, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))

    return render_template('register.html', msg = msg)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    msg = ""
    if request.method == 'POST':
        error = False
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            error = True
            msg = "Invalid email or password. Please try again."
            return render_template('login.html', error = error, msg = msg)
        else:
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))

    return render_template('login.html', error = error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    temp, condition = get_weather(-33.8688, 151.2093)
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', name=user.name, temp=temp, condition=condition)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    file = user.file
    return render_template('settings.html', user=user, name=user.name, file=user.file)

@app.route('/editprofile', methods=['GET', 'POST'])
def editprofile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        filed = request.files.get('file')

        # Validate email uniqueness if changed
        if email and email != user.email:
            if User.query.filter_by(email=email).first():
                return "Email already in use", 400
            user.email = email
        if name:
            user.name = name
        if password:
            user.password = generate_password_hash(password)
        if filed and filed.filename != "":
            filename = secure_filename(filed.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            filed.save(filepath)
            user.file = filename

        db.session.commit()
        return redirect(url_for('settings'))
    

    return render_template('editprofile.html', user=user, name=user.name, email=user.email, file=user.file)

# ------------------- Solar Panel Details -------------------

@app.route('/about')
def about():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    details = {
        'version': '1.0.0',
        'serial_number': 'SP-20250928-001',
        'last_updated': '16/09/2025'
    }
    return render_template('about.html', details=details)

# ------------------- Contact Us -------------------

@app.route('/contact')
def contact():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    details = {
        'website': 'solarpanelsolutions.com',
        'email': 'support@solarpanelsolutions.com',
        'phone': '+61 457 284 421'
    }
    return render_template('contact.html', details=details)

# ------------------- Run App -------------------

if __name__ == '__main__':
    app.run(debug=True)
