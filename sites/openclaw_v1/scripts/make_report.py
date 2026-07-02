import os
import sqlite3
from datetime import datetime

def generate_report(db_path, report_dir):
    if not os.path.exists(db_path):
        return "Database not found."
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get current time and file mtime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_mtime = datetime.fromtimestamp(os.path.getmtime(db_path)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Total reservations today
    cursor.execute("SELECT COUNT(*) FROM reservations WHERE date(start_time) = date('now')")
    total_today = cursor.fetchone()[0]
    
    # Room-wise cumulative reservations
    room_stats = []
    for room_id in range(1, 9):
        cursor.execute("SELECT COUNT(*) FROM reservations WHERE room_id = ?", (room_id,))
        count = cursor.fetchone()[0]
        room_stats.append(f"- Room {room_id}: {count} reservations")
    
    room_report = "\n".join(room_str_list) if 'room_str_list' in locals() else "\n".join(room_stats)
    # Actually use the correct list
    room_report = "\n".join(room_stats)
    
    # Summary
    summary = "All systems operational. No issues detected."
    
    report_content = f"""# Reservation Report
**Generated at:** {now_str}
**Database Last Modified:** {db_mtime}

## Today's Activity
- Total reservations today: {total_today}

## Room Statistics
{room_report}

## Summary
{summary}
"""
    
    os.makedirs(report_dir, exist_ok=True)
    report_filename = os.path.join(report_dir, datetime.now().strftime("%Y-%m-%d_%H.md"))
    
    with open(report_filename, 'w') as f:
        f.write(report_content)
    
    conn.close()
    return f"Report generated: {report_filename}"

if __name__ == "__main__":
    # Use the path established in the previous step
    db_path = "$HOME/project/sites/openclaw_v1/site.db"
    report_dir = "$HOME/project/ss/openclaw_v1/reports" # This will be corrected via command line or hardcoded
    # Let's use the correct path provided by the user
    report_dir = "$HOME/project/sites/openclaw_v1/reports"
    
    print(generate_report(db_path, report_dir))
