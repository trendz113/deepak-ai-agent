"""
agent.py — SQLite-backed task store + AI worker for Deepak AI Agent
"""

import sqlite3
import os
from brain import think

# ── DB setup ─────────────────────────────────────────────────────────────────

DB_PATH = os.getenv("DB_PATH", "tasks.db")

def _get_conn():
    """Return a per-call connection (safe for multi-threaded Flask)."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Called once by main.py on startup."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            task       TEXT    NOT NULL,
            status     TEXT    NOT NULL DEFAULT 'pending',
            output     TEXT,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


# ── Task helpers ──────────────────────────────────────────────────────────────

def add_task(task: str) -> bool:
    """
    Insert a task. Skips duplicates (same text + pending).
    Returns True if inserted, False if it already existed.
    """
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM tasks WHERE task = ? AND status = 'pending'", (task,)
    ).fetchone()
    if existing:
        conn.close()
        return False
    conn.execute(
        "INSERT INTO tasks (task, status) VALUES (?, 'pending')", (task,)
    )
    conn.commit()
    conn.close()
    return True


def get_tasks():
    """Return all pending tasks as a list of dicts."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'pending' ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_tasks():
    """Return ALL tasks (all statuses) as a list of dicts, newest first."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_pending() -> int:
    """Return the number of pending tasks."""
    conn = _get_conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'pending'"
    ).fetchone()[0]
    conn.close()
    return n


def complete_task(task_id: int, output: str = None):
    """Mark a task done and optionally store its output."""
    conn = _get_conn()
    conn.execute(
        "UPDATE tasks SET status = 'done', output = ? WHERE id = ?",
        (output, task_id)
    )
    conn.commit()
    conn.close()


def fail_task(task_id: int, reason: str = None):
    """Mark a task failed with an optional reason."""
    conn = _get_conn()
    conn.execute(
        "UPDATE tasks SET status = 'failed', output = ? WHERE id = ?",
        (reason, task_id)
    )
    conn.commit()
    conn.close()


# ── AI Worker ─────────────────────────────────────────────────────────────────

def run_agent():
    """
    Main agent loop. Picks pending tasks one by one, calls the LLM,
    parses the structured response, and updates the DB.
    Runs continuously (called in a daemon thread by main.py).
    """
    import time

    while True:
        tasks = get_tasks()

        if not tasks:
            time.sleep(10)
            continue

        # Work on the oldest pending task
        current = tasks[0]
        task_id   = current["id"]
        task_text = current["task"]

        # Mark as running
        conn = _get_conn()
        conn.execute("UPDATE tasks SET status = 'running' WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()

        prompt = f"""
You are Deepak AI worker — an autonomous agent that completes tasks and plans ahead.

Current task (ID {task_id}):
{task_text}

All pending tasks:
{tasks}

Do real, useful work on the current task. Then:
1. Create ONE new follow-up task if it makes sense
2. Produce a concrete output (research, plan, code, analysis, etc.)

Reply EXACTLY in this format (no extra text before or after):

NEW_TASK: <short description of the next task, or NONE>
COMPLETE_TASK_ID: {task_id}
ACTION: <one-line summary of what you did>

OUTPUT_FILE: <filename.txt>
CONTENT:
<full useful content here>
"""

        try:
            result = think(prompt)
        except Exception as e:
            fail_task(task_id, str(e))
            time.sleep(5)
            continue

        # ── Parse NEW_TASK ────────────────────────────────────────────────
        if "NEW_TASK:" in result:
            try:
                new_task = result.split("NEW_TASK:")[1].split("\n")[0].strip()
                if new_task and new_task.upper() != "NONE":
                    add_task(new_task)
            except Exception:
                pass

        # ── Parse & save output file ──────────────────────────────────────
        file_output = None
        if "OUTPUT_FILE:" in result and "CONTENT:" in result:
            try:
                filename = result.split("OUTPUT_FILE:")[1].split("\n")[0].strip()
                content  = result.split("CONTENT:")[1].strip()
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"✅ File created: {filename}")
                file_output = content
            except Exception as e:
                print(f"File error: {e}")

        # ── Complete the task ─────────────────────────────────────────────
        if "COMPLETE_TASK_ID:" in result:
            try:
                done_id = int(result.split("COMPLETE_TASK_ID:")[1].split("\n")[0].strip())
                complete_task(done_id, output=file_output or result[:500])
            except Exception:
                complete_task(task_id, output=file_output or result[:500])
        else:
            complete_task(task_id, output=file_output or result[:500])

        time.sleep(3)  # brief pause between tasks
