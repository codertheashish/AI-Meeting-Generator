"""
database.py
------------
Lightweight SQLite data-access layer for AI Meeting Generator.
No ORM is used on purpose so the project has zero extra dependencies
beyond Python's built-in sqlite3 module.
"""

import sqlite3
import os
import json
from datetime import datetime
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "meeting_notes.db")


@contextmanager
def get_db():
    """Context-managed SQLite connection with row factory set to dict-like rows."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all tables if they do not already exist. Safe to call on every boot."""
    os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
    with get_db() as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT 'Untitled Meeting',
                date TEXT,
                duration INTEGER DEFAULT 0,
                audio_file TEXT,
                transcript TEXT,
                summary TEXT,
                key_highlights TEXT,
                status TEXT DEFAULT 'created',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS speakers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                speaking_time INTEGER DEFAULT 0,
                speaking_percentage REAL DEFAULT 0,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS action_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                task TEXT NOT NULL,
                assigned_to TEXT,
                deadline TEXT,
                completed INTEGER DEFAULT 0,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                decision TEXT NOT NULL,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
            )
        """)

        conn.commit()


# ---------------------------------------------------------------- Meetings
def create_meeting(title="Untitled Meeting", date=None, audio_file=None):
    date = date or datetime.now().isoformat(timespec="seconds")
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO meetings (title, date, audio_file, status) VALUES (?, ?, ?, 'created')",
            (title, date, audio_file),
        )
        return cur.lastrowid


def update_meeting(meeting_id, **fields):
    if not fields:
        return
    keys = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [meeting_id]
    with get_db() as conn:
        conn.execute(f"UPDATE meetings SET {keys} WHERE id = ?", values)


def get_meeting(meeting_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        return dict(row) if row else None


def list_meetings():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM meetings ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def delete_meeting(meeting_id):
    with get_db() as conn:
        conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))


# ---------------------------------------------------------------- Speakers
def replace_speakers(meeting_id, speakers):
    """speakers: list of dicts {name, speaking_time, speaking_percentage}"""
    with get_db() as conn:
        conn.execute("DELETE FROM speakers WHERE meeting_id = ?", (meeting_id,))
        for s in speakers:
            conn.execute(
                "INSERT INTO speakers (meeting_id, name, speaking_time, speaking_percentage) VALUES (?, ?, ?, ?)",
                (meeting_id, s.get("name", "Unknown"), s.get("speaking_time", 0), s.get("speaking_percentage", 0)),
            )


def get_speakers(meeting_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM speakers WHERE meeting_id = ? ORDER BY speaking_percentage DESC", (meeting_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ------------------------------------------------------------ Action items
def replace_action_items(meeting_id, items):
    with get_db() as conn:
        conn.execute("DELETE FROM action_items WHERE meeting_id = ?", (meeting_id,))
        for i in items:
            conn.execute(
                "INSERT INTO action_items (meeting_id, task, assigned_to, deadline, completed) VALUES (?, ?, ?, ?, ?)",
                (meeting_id, i.get("task", ""), i.get("assigned_to", ""), i.get("deadline", ""), int(i.get("completed", 0))),
            )


def get_action_items(meeting_id):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM action_items WHERE meeting_id = ? ORDER BY id", (meeting_id,)).fetchall()
        return [dict(r) for r in rows]


def update_action_item(item_id, **fields):
    if not fields:
        return
    keys = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [item_id]
    with get_db() as conn:
        conn.execute(f"UPDATE action_items SET {keys} WHERE id = ?", values)


# --------------------------------------------------------------- Decisions
def replace_decisions(meeting_id, decisions):
    with get_db() as conn:
        conn.execute("DELETE FROM decisions WHERE meeting_id = ?", (meeting_id,))
        for d in decisions:
            conn.execute("INSERT INTO decisions (meeting_id, decision) VALUES (?, ?)", (meeting_id, d))


def get_decisions(meeting_id):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM decisions WHERE meeting_id = ? ORDER BY id", (meeting_id,)).fetchall()
        return [dict(r)["decision"] for r in rows]


# --------------------------------------------------------- Full aggregate
def get_full_meeting(meeting_id):
    meeting = get_meeting(meeting_id)
    if not meeting:
        return None
    meeting["speakers"] = get_speakers(meeting_id)
    meeting["action_items"] = get_action_items(meeting_id)
    meeting["decisions"] = get_decisions(meeting_id)
    if meeting.get("key_highlights"):
        try:
            meeting["key_highlights"] = json.loads(meeting["key_highlights"])
        except (TypeError, json.JSONDecodeError):
            meeting["key_highlights"] = []
    else:
        meeting["key_highlights"] = []
    return meeting
