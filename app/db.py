import sqlite3
from datetime import datetime, timezone
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  due TEXT,                 -- ISO8601 with offset, or NULL
  est_minutes INTEGER NOT NULL DEFAULT 30,
  importance INTEGER NOT NULL DEFAULT 3,   -- 1 (low) .. 5 (critical)
  status TEXT NOT NULL DEFAULT 'todo',     -- todo | done
  source TEXT NOT NULL DEFAULT 'web',
  created_at TEXT NOT NULL,
  slot_start TEXT,          -- UTC ISO
  slot_end TEXT,
  event_id TEXT             -- Outlook event id
);
"""

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def add_task(title, due=None, est_minutes=30, importance=3, source="web"):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO tasks(title,due,est_minutes,importance,source,created_at) VALUES (?,?,?,?,?,?)",
            (title, due, est_minutes, importance, source, now_iso()),
        )
        return cur.lastrowid

def list_tasks(status="todo"):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM tasks WHERE status=? ORDER BY id", (status,))]

def get_task(task_id):
    with conn() as c:
        r = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(r) if r else None

def update_task(task_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE tasks SET {cols} WHERE id=?", (*fields.values(), task_id))

def delete_task(task_id):
    with conn() as c:
        c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
