"""
Database layer for AI Meeting Notes Generator - Postgres edition.

Rewritten from the original SQLite version to run on Vercel's serverless
Python functions, whose filesystem is read-only (except /tmp, which is
wiped between invocations) - so a local .db file can't persist data across
requests. Any Postgres works: Vercel Postgres (Neon), Supabase, Railway,
Neon directly, etc. Set DATABASE_URL in your environment.

Query placeholders use psycopg2's %s style (not SQLite's ?). Comparisons
against a possibly-NULL parameter use "IS NOT DISTINCT FROM %s" instead of
"= %s", because standard SQL's "=" never matches NULL, and Postgres (unlike
SQLite) doesn't accept a bound parameter on the right-hand side of "IS".
"""
import os
import json
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. On Vercel, add a Postgres integration "
            "(Vercel Postgres / Neon / Supabase all work) and set DATABASE_URL "
            "in your project's Environment Variables."
        )
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def init_db():
    """Create all tables if they do not already exist, and migrate old schemas."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users (id) ON DELETE CASCADE,
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
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS speakers (
            id SERIAL PRIMARY KEY,
            meeting_id INTEGER NOT NULL REFERENCES meetings (id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            speaking_time INTEGER DEFAULT 0,
            speaking_percentage REAL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS action_items (
            id SERIAL PRIMARY KEY,
            meeting_id INTEGER NOT NULL REFERENCES meetings (id) ON DELETE CASCADE,
            task TEXT NOT NULL,
            assigned_to TEXT,
            deadline TEXT,
            priority TEXT DEFAULT 'Medium',
            completed INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    _migrate_schema(conn)
    cur.close()
    conn.close()


def _migrate_schema(conn):
    """
    Lightweight migration for databases created before this update, so
    upgrading doesn't require dropping the existing tables.
    """
    cur = conn.cursor()

    def add_column_if_missing(table, column, ddl):
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            (table, column),
        )
        if not cur.fetchone():
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    add_column_if_missing("meetings", "follow_up_points", "follow_up_points TEXT")
    add_column_if_missing("action_items", "priority", "priority TEXT DEFAULT 'Medium'")
    add_column_if_missing("meetings", "user_id", "user_id INTEGER REFERENCES users (id) ON DELETE CASCADE")
    conn.commit()
    cur.close()


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def create_user(email, name="", password_hash=None, oauth_provider=None, oauth_id=None, avatar_url=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (email, name, password_hash, oauth_provider, oauth_id, avatar_url, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (email.lower().strip(), name, password_hash, oauth_provider, oauth_id, avatar_url, _now()),
    )
    user_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return user_id


def get_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", (email.lower().strip(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_user_by_oauth(provider, oauth_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE oauth_provider = %s AND oauth_id = %s", (provider, oauth_id))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def update_user_password(user_id, password_hash):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
    conn.commit()
    cur.close()
    conn.close()


def link_oauth_to_user(user_id, provider, oauth_id, avatar_url=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET oauth_provider = %s, oauth_id = %s, avatar_url = COALESCE(%s, avatar_url) WHERE id = %s",
        (provider, oauth_id, avatar_url, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()


# ---------------------------------------------------------------------------
# Meeting helpers
# ---------------------------------------------------------------------------

def create_meeting(title="Untitled Meeting", audio_file=None, user_id=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO meetings (user_id, title, date, audio_file, status, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (user_id, title, _now(), audio_file, "created", _now()),
    )
    meeting_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
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

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [meeting_id]
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE meetings SET {set_clause} WHERE id = %s", values)
    conn.commit()
    cur.close()
    conn.close()


def get_meeting(meeting_id, user_id=None):
    """
    user_id=None means "anonymous/guest" - matches only meetings with no
    owner (user_id IS NULL), never another logged-in user's meetings.
    "IS NOT DISTINCT FROM" (not "=") is used because Postgres treats NULL
    as never equal to anything, including another NULL, under "=".
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM meetings WHERE id = %s AND user_id IS NOT DISTINCT FROM %s",
        (meeting_id, user_id),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return _meeting_to_dict(row)


def list_meetings(user_id=None):
    """user_id=None lists only guest (unowned) meetings - see get_meeting()."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM meetings WHERE user_id IS NOT DISTINCT FROM %s ORDER BY created_at DESC",
        (user_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [_meeting_to_dict(r) for r in rows]


def delete_meeting(meeting_id, user_id=None):
    """user_id=None deletes only from guest (unowned) meetings - see get_meeting()."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM meetings WHERE id = %s AND user_id IS NOT DISTINCT FROM %s",
        (meeting_id, user_id),
    )
    conn.commit()
    cur.close()
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
    cur = conn.cursor()
    cur.execute("DELETE FROM speakers WHERE meeting_id = %s", (meeting_id,))
    for s in speakers:
        cur.execute(
            "INSERT INTO speakers (meeting_id, name, speaking_time, speaking_percentage) VALUES (%s, %s, %s, %s)",
            (meeting_id, s.get("name", "Unknown"), s.get("speaking_time", 0), s.get("speaking_percentage", 0)),
        )
    conn.commit()
    cur.close()
    conn.close()


def get_speakers(meeting_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM speakers WHERE meeting_id = %s", (meeting_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Action items
# ---------------------------------------------------------------------------

def replace_action_items(meeting_id, items):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM action_items WHERE meeting_id = %s", (meeting_id,))
    for item in items:
        cur.execute(
            "INSERT INTO action_items (meeting_id, task, assigned_to, deadline, priority, completed) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (meeting_id, item.get("task", ""), item.get("assigned_to", ""),
             item.get("deadline", ""), item.get("priority") or "Medium", int(item.get("completed", 0))),
        )
    conn.commit()
    cur.close()
    conn.close()


def get_action_items(meeting_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM action_items WHERE meeting_id = %s", (meeting_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def action_item_belongs_to_user(item_id, user_id):
    """Used by the API layer to make sure a user can only edit their own action items."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT m.user_id FROM action_items a JOIN meetings m ON a.meeting_id = m.id WHERE a.id = %s",
        (item_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row) and row["user_id"] == user_id


def update_action_item(item_id, **fields):
    allowed = {"task", "assigned_to", "deadline", "priority", "completed"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [item_id]
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE action_items SET {set_clause} WHERE id = %s", values)
    conn.commit()
    cur.close()
    conn.close()
