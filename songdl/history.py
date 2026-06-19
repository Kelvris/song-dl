import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.expanduser('~/.config/song-dl/history.db')


def _get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT UNIQUE,
            url TEXT,
            title TEXT,
            artist TEXT,
            album TEXT,
            filepath TEXT,
            format TEXT,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def check_history(video_id):
    conn = _get_db()
    cur = conn.execute("SELECT 1 FROM downloads WHERE video_id = ?", (video_id,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def record_history(video_id, url, title, artist, album, filepath, format):
    conn = _get_db()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("""
        INSERT INTO downloads
            (video_id, url, title, artist, album, filepath, format, downloaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id) DO UPDATE SET
            url=excluded.url, title=excluded.title, artist=excluded.artist,
            album=excluded.album, filepath=excluded.filepath, format=excluded.format,
            downloaded_at=excluded.downloaded_at
    """, (video_id, url, title, artist, album, filepath, format, now))
    conn.commit()
    conn.close()


def show_history(limit=25):
    conn = _get_db()
    cur = conn.execute("""
        SELECT downloaded_at, title, artist, album, filepath
        FROM downloads
        ORDER BY downloaded_at DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("No download history yet.")
        return

    sep = '-' * 111
    print(f"{'Date':<19} {'Title':<36} {'Artist':<28} {'Album':<26}")
    print(sep)
    for row in rows:
        date, title, artist, album, filepath = row
        date = (date or '')[:19]
        title = (title or '')[:36]
        artist = (artist or '')[:28]
        album = (album or '')[:26]
        print(f"{date:<19} {title:<36} {artist:<28} {album:<26}")
