# db.py
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "gelikon.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            name TEXT,
            instrument TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            event_name TEXT,
            date TEXT,
            start_time TEXT,
            end_time TEXT,
            hall TEXT,
            event_type TEXT,
            role TEXT,
            calendar_event_id TEXT,
            FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        )
    """)
    conn.commit()
    conn.close()

def get_user(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name, instrument FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row  # (name, instrument) or None

def create_or_update_user(telegram_id, name="Медведев О.", instrument="фагот"):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (telegram_id, name, instrument)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET name = ?, instrument = ?
    """, (telegram_id, name, instrument, name, instrument))
    conn.commit()
    conn.close()

def add_event(telegram_id, event_data):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO events (
            telegram_id, event_name, date, start_time, end_time, hall, event_type, role, calendar_event_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        telegram_id,
        event_data["event_name"],
        event_data["date"],
        event_data["start_time"],
        event_data["end_time"],
        event_data["hall"],
        event_data["event_type"],
        event_data["role"],
        event_data.get("calendar_event_id", "")
    ))
    conn.commit()
    conn.close()

def delete_event(user_id: int, event_name: str, date: str) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT calendar_event_id FROM events
        WHERE telegram_id = ? AND event_name = ? AND date = ?
    """, (user_id, event_name, date))
    row = cursor.fetchone()

    if row:
        cal_id = row[0]
        cursor.execute("""
            DELETE FROM events
            WHERE telegram_id = ? AND event_name = ? AND date = ?
        """, (user_id, event_name, date))
        conn.commit()
        conn.close()
        return cal_id
    else:
        conn.close()
        return None

def _get_week_range(date):
    """Возвращает (monday, sunday) для недели, содержащей date."""
    monday = date - timedelta(days=date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday

def get_events_for_current_week(telegram_id):
    today = datetime.today().date()
    monday, sunday = _get_week_range(today)
    return _fetch_events(telegram_id, monday, sunday)

def get_events_for_next_week(telegram_id):
    today = datetime.today().date()
    next_monday = today + timedelta(days=(7 - today.weekday()))
    next_sunday = next_monday + timedelta(days=6)
    return _fetch_events(telegram_id, next_monday, next_sunday)

def _fetch_events(telegram_id, start_date, end_date):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT event_name, date, start_time, end_time, hall, event_type
        FROM events
        WHERE telegram_id = ? AND date BETWEEN ? AND ?
        ORDER BY date, start_time
    """, (telegram_id, str(start_date), str(end_date)))
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "event": r[0],
            "date": r[1],
            "start": r[2],
            "end": r[3],
            "hall": r[4],
            "type": r[5]
        }
        for r in rows
    ]
