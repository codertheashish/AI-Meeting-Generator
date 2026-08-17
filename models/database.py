"""
Database layer for AI Meeting Notes Generator.
Uses plain sqlite3 (no ORM) so the project has zero extra dependencies
beyond what's in requirements.txt.
"""
import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "meeting_notes.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not already exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            password_hash TEXT,
            oauth_provider TEXT,
            oauth_id TEXT,
            avatar_url TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL DEFAULT 'Untitled Meeting',
            date TEXT NOT NULL,
            duration INTEGER DEFAULT 0,
            audio_file TEXT,
            transcript TEXT,
            summary TEXT,
            key_highlights TEXT,
            decisions TEXT,
            follow_up_points TEXT,
            status TEXT DEFAULT 'created',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS speakers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            speaking_time INTEGER DEFAULT 0,
            speaking_percentage REAL DEFAULT 0,
            FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS action_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            task TEXT NOT NULL,
            assigned_to TEXT,
            deadline TEXT,
            priority TEXT DEFAULT 'Medium',
            completed INTEGER DEFAULT 0,
            FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            decision TEXT NOT NULL,
            FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    _migrate_schema(conn)
    conn.close()


def _migrate_schema(conn):
    """
    Lightweight migration for databases created before this update, so
    upgrading the app doesn't require deleting the existing .db file.
    Adds any columns that were introduced after the original CREATE TABLE.
    """
    def add_column_if_missing(table, column, ddl):
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    add_column_if_missing("meetings", "follow_up_points", "follow_up_points TEXT")
    add_column_if_missing("action_items", "priority", "priority TEXT DEFAULT 'Medium'")
    add_column_if_missing("meetings", "user_id", "user_id INTEGER")
    conn.commit()


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def create_user(email, name="", password_hash=None, oauth_provider=None, oauth_id=None, avatar_url=None):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO users (email, name, password_hash, oauth_provider, oauth_id, avatar_url, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (email.lower().strip(), name, password_hash, oauth_provider, oauth_id, avatar_url, now),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_oauth(provider, oauth_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE oauth_provider = ? AND oauth_id = ?", (provider, oauth_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_password(user_id, password_hash):
    conn = get_connection()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()
    conn.close()


def link_oauth_to_user(user_id, provider, oauth_id, avatar_url=None):
    conn = get_connection()
    conn.execute(
        "UPDATE users SET oauth_provider = ?, oauth_id = ?, avatar_url = COALESCE(?, avatar_url) WHERE id = ?",
        (provider, oauth_id, avatar_url, user_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Meeting helpers
# ---------------------------------------------------------------------------

def create_meeting(title="Untitled Meeting", audio_file=None, user_id=None):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO meetings (user_id, title, date, audio_file, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, title, now, audio_file, "created", now),
    )
    conn.commit()
    meeting_id = cur.lastrowid
    conn.close()
    return meeting_id


def update_meeting(meeting_id, **fields):
    if not fields:
        return
    allowed = {"title", "date", "duration", "audio_file", "transcript", "summary",
               "key_highlights", "decisions", "follow_up_points", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    # JSON-encode list fields
    for key in ("key_highlights", "decisions", "follow_up_points"):
        if key in updates and isinstance(updates[key], (list, dict)):
            updates[key] = json.dumps(updates[key])

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [meeting_id]
    conn = get_connection()
    conn.execute(f"UPDATE meetings SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_meeting(meeting_id, user_id=None):
    """
    user_id=None means "anonymous/guest" - matches only meetings with no
    owner (user_id IS NULL), never another logged-in user's meetings.
    Uses "IS" instead of "=" because SQL's "=" never matches NULL.
    """
    conn = get_connection()
    row = conn.execute("SELECT * FROM meetings WHERE id = ? AND user_id IS ?", (meeting_id, user_id)).fetchone()
    conn.close()
    if not row:
        return None
    return _meeting_to_dict(row)


def list_meetings(user_id=None):
    """user_id=None lists only guest (unowned) meetings - see get_meeting()."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM meetings WHERE user_id IS ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [_meeting_to_dict(r) for r in rows]


def delete_meeting(meeting_id, user_id=None):
    """user_id=None deletes only from guest (unowned) meetings - see get_meeting()."""
    conn = get_connection()
    conn.execute("DELETE FROM meetings WHERE id = ? AND user_id IS ?", (meeting_id, user_id))
    conn.commit()
    conn.close()


def _meeting_to_dict(row):
    d = dict(row)
    for key in ("key_highlights", "decisions", "follow_up_points"):
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except (TypeError, json.JSONDecodeError):
                d[key] = []
        else:
            d[key] = []
    d["speakers"] = get_speakers(d["id"])
    d["action_items"] = get_action_items(d["id"])
    return d


# ---------------------------------------------------------------------------
# Speakers
# ---------------------------------------------------------------------------

def replace_speakers(meeting_id, speakers):
    """speakers: list of dicts with name, speaking_time, speaking_percentage"""
    conn = get_connection()
    conn.execute("DELETE FROM speakers WHERE meeting_id = ?", (meeting_id,))
    for s in speakers:
        conn.execute(
            "INSERT INTO speakers (meeting_id, name, speaking_time, speaking_percentage) VALUES (?, ?, ?, ?)",
            (meeting_id, s.get("name", "Unknown"), s.get("speaking_time", 0), s.get("speaking_percentage", 0)),
        )
    conn.commit()
    conn.close()


def get_speakers(meeting_id):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM speakers WHERE meeting_id = ?", (meeting_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Action items
# ---------------------------------------------------------------------------

def replace_action_items(meeting_id, items):
    conn = get_connection()
    conn.execute("DELETE FROM action_items WHERE meeting_id = ?", (meeting_id,))
    for item in items:
        conn.execute(
            "INSERT INTO action_items (meeting_id, task, assigned_to, deadline, priority, completed) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (meeting_id, item.get("task", ""), item.get("assigned_to", ""),
             item.get("deadline", ""), item.get("priority") or "Medium", int(item.get("completed", 0))),
        )
    conn.commit()
    conn.close()


def get_action_items(meeting_id):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM action_items WHERE meeting_id = ?", (meeting_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def action_item_belongs_to_user(item_id, user_id):
    """Used by the API layer to make sure a user can only edit their own action items."""
    conn = get_connection()
    row = conn.execute(
        "SELECT m.user_id FROM action_items a JOIN meetings m ON a.meeting_id = m.id WHERE a.id = ?",
        (item_id,),
    ).fetchone()
    conn.close()
    return bool(row) and row["user_id"] == user_id


def update_action_item(item_id, **fields):
    allowed = {"task", "assigned_to", "deadline", "priority", "completed"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [item_id]
    conn = get_connection()
    conn.execute(f"UPDATE action_items SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

def replace_decisions(meeting_id, decisions):
    conn = get_connection()
    conn.execute("DELETE FROM decisions WHERE meeting_id = ?", (meeting_id,))
    for d in decisions:
        text = d if isinstance(d, str) else d.get("decision", "")
        conn.execute("INSERT INTO decisions (meeting_id, decision) VALUES (?, ?)", (meeting_id, text))
    conn.commit()
    conn.close()


def get_decisions(meeting_id):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM decisions WHERE meeting_id = ?", (meeting_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
