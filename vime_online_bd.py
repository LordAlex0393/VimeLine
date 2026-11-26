import os
import time
import sqlite3
import requests
from datetime import datetime, timedelta

API = "https://api.vimeworld.com"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "vime_stats.db")
INTERVAL_MINUTES = 10


def get_json(url, timeout=10):
    for attempt in range(5):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            if attempt == 4:
                raise
            time.sleep(5)



def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS total_online (
                timestamp TEXT PRIMARY KEY,
                total INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mode_online (
                timestamp TEXT,
                mode_key TEXT,
                count INTEGER,
                PRIMARY KEY (timestamp, mode_key)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mode_time 
            ON mode_online (mode_key, timestamp)
        """)
        conn.commit()


def save_tick(timestamp_str):
    online = get_json(f"{API}/online")
    total = online.get("total", 0)
    separated = online.get("separated", {})

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO total_online (timestamp, total) VALUES (?, ?)",
            (timestamp_str, total)
        )
        rows = [(timestamp_str, mode_key, count) for mode_key, count in separated.items()]
        cursor.executemany(
            "INSERT OR REPLACE INTO mode_online (timestamp, mode_key, count) VALUES (?, ?, ?)",
            rows
        )
        conn.commit()
    print(f"[{timestamp_str}] Записано! Общий онлайн: {total}, режимов: {len(separated)}")


def main():
    init_db()
    print(f"База данных: {DB_FILE}")

    # Сразу первый замер при запуске
    now = datetime.now()
    first_ts = now.replace(minute=(now.minute // INTERVAL_MINUTES) * INTERVAL_MINUTES, second=0, microsecond=0)
    save_tick(first_ts.strftime("%Y-%m-%d %H:%M:%S"))

    # Дальше каждые 10 минут строго в ровное время
    while True:
        now = datetime.now()
        minutes_to_add = INTERVAL_MINUTES - (now.minute % INTERVAL_MINUTES)
        next_run = (now + timedelta(minutes=minutes_to_add)).replace(second=0, microsecond=0)
        sleep_sec = (next_run - now).total_seconds()
        print(f"Ждем до {next_run.strftime('%H:%M:%S')} ({int(sleep_sec)} сек.)...")
        time.sleep(sleep_sec)
        try:
            save_tick(next_run.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            print(f"[{next_run.strftime('%Y-%m-%d %H:%M:%S')}] Ошибка: {e}")


if __name__ == "__main__":
    main()
