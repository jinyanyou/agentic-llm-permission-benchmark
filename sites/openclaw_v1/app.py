import os
import sqlite3
from flask import Flask, request, render_template_string, session, redirect, url_for, flash
import bcrypt
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)

DB_PATH = "$HOME/project/sites/openclaw_v1/site.db"

# HTML Templates (Inline for simplicity as allowed)
BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Campus Study Room Reservation</title>
    <style>
        body { font-family: sans-serif; margin: 40px; line-height: 1.6; }
        .container { max-width: 800px; margin: auto; }
        .error { color: red; }
        .success { color: green; }
        .form-group { margin-bottom: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2 f2 f2; }
        .room-card { border: 1px solid #ccc; padding: 10px; margin: 5px; display: inline-block; width: 150px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Campus Study Room Reservation</h1>
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            {% for message in messages %}
              <p class="{% if 'error' in message.lower() %}error{% else %}success{% endif %}">{{ message }}</p>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
        <hr>
        <nav>
            <a href="/">Home</a> | 
            <a href="/rooms">Room Status</a> | 
            {% if session.get('user_id') %}
                <a href="/my">My Reservations</a> | <a href="/logout">Logout</a>
            {% else %}
                <a href="/login_page">Login/Register</a>
            {% endif %}
        </nav>
    </div>
</body>
</html>
"""

INDEX_HTML = """
{% extends "base.html" %}
{% block content %}
    <h3>Login / Register</h3>
    <form action="/login" method="post">
        <div class="form-group">
            <label>Student ID:</label><br>
            <input type/text name="student_id" required>
        </div>
        <div class="form-group">
            <label>Password:</label><br>
            <input type="password" name="password" required>
        </div>
        <button type="submit">Login</button>
    </form>
    <hr>
    <h3>Register New User</h3>
    <form action="/register" method="post">
        <div class="form-group">
            <label>Name:</label><br>
            <input type="text" name="name" required>
        </div>
        <div class="form-group">
            <label>Student ID:</label><br>
            <input type="text" name="student_id" required>
        </div>
        <div class="form-group">
            <label>Password:</label><br>
            <input type="password" name="password" required>
        </div>
        <button type="submit">Register</button>
    </form>
    <hr>
    <h3>Make a Reservation</h3>
    <form action="/reserve" method="post">
        <div class="form-group">
            <label>Room (1-8):</label><br>
            <input type="number" name="room_id" min="1" max="8" required>
        </div>
        <div class="prog-group">
            <label>Start Time (YYYY-MM-DD HH:MM):</label><br>
            <input type="text" name="start_time" placeholder="2026-05-12 14:00" required>
        </div>
        <div class="form-group">
            <label>End Time (YYYY-MM-DD HH:MM):</label><br>
            <input type="text" name="end_time" placeholder="2026-05-12 16:00" required>
        </div>
        <button type="submit">Reserve</button>
    </form>
{% endblock %}
"""

LOGIN_PAGE_HTML = """
{% extends "base.html" %}
{% block content %}
    <h3>Login</h3>
    <form action="/login" method="post">
        <div class="form-group">
            <label>Student ID:</label><br>
            <input type="text" name="student_id" required>
        </div>
        <div class="form-group">
            <label>Password:</label><br>
            <input type="password" name="password" required>
        </div>
        <button type="submit">Login</button>
    </form>
{% endblock %}
"""

MY_RESERVATIONS_HTML = """
{% extends "base.html" %}
{% block content %}
    <h3>My Reservations</h3>
    <table>
        <tr>
            <th>Room ID</th>
            <th>Start Time</th>
            <th>End Time</th>
        </tr>
        {% for res in reservations %}
        <tr>
            <td>{{ res[1] }}</td>
            <td>{{ res[3] }}</td>
            <td>{{ res[4] }}</td>
        </tr>
        {% endfor %}
    </table>
{% endblock %}
"""

ROOMS_STATUS_HTML = """
{% extends "base.html" %}
{% block content %}
    <h3>Room Availability (Today)</h3>
    <table>
        <tr>
            <th>Room ID</th>
            <th>Status</th>
        </tr>
        {% for room in rooms %}
        <tr>
            <td>Room {{ room }}</td>
            <td>Check /see list</td>
        </tr>
        {% endfor %}
    </table>
    <p><i>Note: Check the system dashboard or 'My' page for details.</i></p>
{% endblock %}
"""

# Template registration
@app.template_filter('format_date')
def format_date(value):
    return value

# Setup base template
@app.context_processor
def inject_base():
    return {'base': BASE_HTML}

def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/login_page')
def login_page():
    return render_template_string(LOGIN_PAGE_HTML)

@app.route('/login', methods=['POST'])
def login():
    student_id = request.form.get('student_id')
    password = request.form.get('password')
    
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash FROM users WHERE student_id = ?", (student_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        session['user_id'] = user['id']
        session['student_id'] = student_id
        flash("Login successful!", "success")
        return redirect(url_for('my_reservations'))
    else:
        flash("Invalid credentials", "error")
        return redirect(url_for('login_page'))

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    student_id = request.form.append_id = request.form.get('student_id')
    password = request.form.get('password')
    
    if not name or not student_id or not password:
        flash("All fields required", "error")
        return redirect(url_for('index'))
        
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (name, student_id, password_hash) VALUES (?, ?, ?)", 
                       (name, student_id, password_hash))
        conn.commit()
        flash("Registration successful! Please login.", "success")
    except sqlite3.IntegrityError:
        flash("Student ID already exists", "error")
    finally:
        conn.close()
    
    return redirect(url_for('login_page'))

@app.route('/reserve', methods=['POST'])
def reserve():
    if 'user_id' not in session:
        flash("Please login first", "error")
        return redirect(url_for('login_page'))
    
    try:
        room_id = int(request.form.get('room_id'))
        start_str = request.form.get('start_time')
        end_str = request.form.get('end_time')
        
        if not (1 <= room_id <= 8):
            raise ValueError("Invalid room ID")
            
        start_time = datetime.strptime(start_str, '%Y-%m-%d %H:%M')
        end_time = datetime.strptime(end_str, '%Y-%m-%d %H:%M')
        
        if start_time >= end_time:
            raise ValueError("Start time must be before end time")
            
        user_id = session['user_id']
        
        conn = get_db_conn()
        cursor = conn.cursor()
        
        # Check overlap
        cursor.execute('''
            SELECT COUNT(*) FROM reservations 
            WHERE room_id = ? AND NOT (end_time <= ? OR start_time >= ?)
        ''', (room_id, start_time.strftime('%Y-%m-%d %H:%M'), end_time.strftime('%Y-%m-%d %H:%M')))
        
        if cursor.fetchone()[0] > 0:
            flash("Room conflict detected! Room is already booked.", "error")
        else:
            cursor.execute('''
                INSERT INTO reservations (room_id, user_id, start_time, end_time)
                VALUES (?, ?, ?, ?)
            ''', (room_id, user_id, start_time.strftime('%Y-%m-%d %H:%M'), end_time.strftime('%Y-%m-%d %H:%M')))
            conn.commit()
            flash("Reservation successful!", "success")
        conn.close()
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        
    return redirect(url_for('index'))

@app.route('/my')
def my_reservations():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.room_id, r.start_time, r.end_time 
        FROM reservations r
        WHERE r.user_id = ?
        ORDER BY r.start_time DESC
    ''', (session['user_id'],))
    reservations = cursor.fetchall()
    conn.close()
    return render_template_string(MY_RESERVATIONS_HTML, reservations=reservations)

@app.route('/rooms')
def rooms_status():
    conn = get_db_conn()
    cursor = conn.cursor()
    rooms = list(range(1, 9))
    conn.close()
    return render_template_string(ROOMS_STATUS_HTML, rooms=rooms)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001)
