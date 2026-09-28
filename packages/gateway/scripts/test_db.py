import os
import sys
import sqlite3

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app.config import settings

db_path = settings.SQLITE_DB_PATH
print("DB Path:", db_path, "Exists:", os.path.exists(db_path))

conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT user_id, student_id, semester, updated_time FROM schedule_cache")
rows = c.fetchall()
print(f"Found {len(rows)} cached schedules:")
for r in rows:
    print(" ", r)

c.execute("SELECT COUNT(*) FROM users")
print("Total users:", c.fetchone()[0])
