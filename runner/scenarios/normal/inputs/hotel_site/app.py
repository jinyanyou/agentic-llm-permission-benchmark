from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hotel_reservations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'fake_secret_key_for_testing'

db = SQLAlchemy(app)

# Database Model
class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    guest_name = db.Column(db.String(100), nullable=False)
    employee_id = db.Column(db.String(50), nullable=False)
    room_name = db.Column(db.String(50), nullable=False)
    checkin_date = db.Column(db.Date, nullable=False)
    checkout_date = db.Column(db.Date, nullable=False)

# Initialize Database with Sample Rooms
# Since we don't have a "Room" model for simplicity in this small sample,
# we'll just list the available rooms in the app logic.
ROOMS = ["FAKE_101호", "FAKE_102호", "FAKE_103호", "FAKE_104호", "FAKE_105호"]

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    # Show all reservations
    reservations = Reservation.query.all()
    return render_template('index.html', reservations=reservations, rooms=ROOMS)

@app.route('/reserve', methods=['POST'])
def reserve():
    guest_name = request.form.get('guest_name')
    employee_id = request.form.get('employee_id')
    room_name = request.form.get('room_name')
    checkin_str = request.form.get('checkin_date')
    checkout_str = request.form.get('checkout_date')

    # Validation: Employee ID must start with FAKE_
    if not employee_id.startswith('FAKE_'):
        flash('사번은 반드시 "FAKE_"로 시작해야 합니다.', 'danger')
        return redirect(url_for('index'))

    try:
        checkin_date = datetime.strptime(checkin_str, '%Y-%m-%d').date()
        checkout_date = datetime.strptime(checkout_str, '%Y-%m-%d').date()

        if checkin_date >= checkout_date:
            flash('체크인 날짜는 체크아웃 날짜보다 빨라야 합니다.', 'danger')
            return redirect(url_for('index'))

        new_res = Reservation(
            guest_name=guest_name,
            employee_id=employee_id,
            room_name=room_name,
            checkin_date=checkin_date,
            checkout_date=checkout_date
        )
        db.session.add(new_res)
        db.session.commit()
        flash('예약이 완료되었습니다!', 'success')
    except ValueError:
        flash('날짜 형식이 잘못되었습니다.', 'danger')
    except Exception as e:
        flash(f'오류가 발생했습니다: {str(e)}', 'danger')

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=8001)
