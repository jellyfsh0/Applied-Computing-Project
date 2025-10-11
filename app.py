from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from datetime import datetime
import os
import random
from werkzeug.utils import secure_filename  # Import all libraries

# Folder where profile pictures are stored
UPLOAD_FOLDER = 'static/uploads'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize Flask app and configuration
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///solar.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Initialize database
db = SQLAlchemy(app)

# Function to find weather data from Open-Meteo API and calculates solar panel output, efficiency, etc.
def get_weather(latitude, longitude, panel_area=1.6, panel_efficiency=0.20):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code,shortwave_radiation",
        "timezone": "auto"
    }

    response = requests.get(url, params=params)
    data = response.json()

    # Get weather data
    current = data.get("current", {})
    temperature = current.get('temperature_2m')
    weather_code = current.get('weather_code')
    timenow = current.get('time')
    time = datetime.fromisoformat(str(timenow))

    # Weather codes
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
    max_output = 4000
    hour = time.hour

    if 6 <= hour <= 18:
        time_factor = max(0, 1 - ((hour - 12) ** 2) / 49)
    else:
        time_factor = 0

    weather_factors = {
        0: 1.0,   
        1: 0.9,   
        2: 0.7,   
        3: 0.5,  
        45: 0.3,  
        48: 0.3,  
        51: 0.6,  
        53: 0.5,
        55: 0.4,  
        61: 0.5,  
        63: 0.4,  
        65: 0.3,  
        66: 0.3,
        67: 0.2,
        71: 0.4,  
        73: 0.3,  
        75: 0.2, 
        77: 0.2,
        80: 0.5,
        81: 0.4,
        82: 0.3,
        85: 0.3,
        86: 0.2,
        95: 0.2,
        96: 0.15,  
        99: 0.1,   
    }
    weather_factor = weather_factors.get(weather_code, 1.0)
    noise = random.uniform(0.95, 1.05)
    output = max_output * time_factor * weather_factor * noise
    irradiance = 2000 * time_factor * weather_factor

    if irradiance and irradiance > 0:
        theoretical_power = irradiance * panel_area * panel_efficiency
        efficiency = (output / theoretical_power) * 100
        efficiency = min(efficiency, 100)
    else:
        efficiency = 0

    co2_saved = (output / 1000) * 0.85

    uptime = "Active" if output > 10 else "Idle"

    return temperature, condition, efficiency, int(output), int(co2_saved), uptime


# Database model for User
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)  
    name = db.Column(db.String(100))              
    email = db.Column(db.String(100), unique=True)  
    password = db.Column(db.String(200))          
    file = db.Column(db.String(200), default='default.png')  

# Create all database tables
with app.app_context():
    db.create_all()

# Home route: redirect to dashboard if logged in, else to login
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Register page, asks for name, email, password, confirm password and creates new user
@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ""
    if request.method == 'POST':
        name = request.form.get('regName')
        email = request.form.get('regEmail')
        password = request.form.get('regPassword')
        confpassword = request.form.get('confPassword')
        if password != confpassword:
            msg = "Passwords must match"  # Validate if passwords match
            return render_template('register.html', msg=msg)
        if not name or not email or not password:
            msg = "Please fill all fields"  # Ensures all fields are filled
            return render_template('register.html', msg=msg)
        if User.query.filter_by(email=email).first():
            msg = "Email already exists"  # Check if email already exists
            return render_template('register.html', msg=msg)
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(name=name, email=email, password=hashed_password)
            db.session.add(new_user)  # Create new user and add to database
            db.session.commit()
            return redirect(url_for('login'))

    return render_template('register.html', msg=msg)

# Login page, asks for email and password, validates user and creates session
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
            return render_template('login.html', error=error, msg=msg)
        else:
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))

    return render_template('login.html', error = error)


# Logout route, clears user session and redirects to login
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Error handler for file too large
@app.errorhandler(413)
def handle_file_too_large(error):
    return "File is too large!", 413

# Dashboard page, shows weather data and solar panel output, efficiency, etc.
@app.route('/dashboard')
def dashboard():
    temp, condition, efficiency, output, co2Saved, uptimePercentage = get_weather(-37.75, 145.03)
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', 
                           name=user.name, 
                           temp=temp, 
                           condition=condition, 
                           efficiency=efficiency,
                           output=output,
                           co2Saved=co2Saved,
                           uptimePercentage=uptimePercentage,)

# Settings page, shows user profile details and option to edit profile
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id']) # Fetch user from database
    return render_template('settings.html', user=user, name=user.name, file=user.file)

# Edit profile page, allows user to input and update name, email, password, and profile picture
@app.route('/editprofile', methods=['GET', 'POST'])
def editprofile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email') 
        password = request.form.get('password')
        photo = request.files.get('file')
        if email and email != user.email:
            if User.query.filter_by(email=email).first():
                return "Email already in use", 400
            user.email = email
        if name:
            user.name = name
        if password:
            user.password = generate_password_hash(password)
        if photo:
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.file = filename

        db.session.commit()
        return redirect(url_for('settings'))

    return render_template('editprofile.html', user=user, name=user.name, email=user.email, file=user.file)

# About page, shows solar panel details
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

# Contact page, shows support contact info
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

# Runs the app
if __name__ == '__main__':
    app.run(debug=True)

