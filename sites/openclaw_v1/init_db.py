import os
import sqlite3
from datetime_utils import get_now_str

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            student_id TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Reservations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    db_path = "$HOME/project/sites/openclaw_v1/site.db"
    init_db(db_path)
    print(f"Database initialized at {db_path}")
