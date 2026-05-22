"""
agent.py — Supervisor + Worker Agent System
Supervisor picks daily goals, breaks into tasks, assigns to specialist workers.
Workers run up to 3 in parallel. Results pushed to GitHub.
"""

import sqlite3
import os
import json
import base64
import urllib.request
import urllib.error
import threading
import time
from datetime import datetime
from brain import think

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH       = os.getenv("DB_PATH", "tasks.db")
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO   = os.getenv("GITHUB_REPO", "")   # e.g. "trendz113/deepak-ai-agent"

WORKER_TYPES  = ["research", "builder", "marketing", "outreach"]
MAX_PARALLEL  = 3

# ── GitHub ────────────────────────────────────────────────────────────────────

def push_to_github(filename: str, content: str, commit_msg: str = None) -> dict:
    """Create or update a file in the GitHub repo via the REST API."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return {"ok": False, "error": "GITHUB_TOKEN or GITHUB_REPO not set"}

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type":  "application/json",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "deepak-ai-agent",
    }

    # Check if file already exists (need sha for updates)
    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            sha = json.loads(resp.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return {"ok": False, "error": f"GET error {e.code}"}

    payload = {
        "message": commit_msg or f"agent: {filename}",
        "content": base64.b64encode(content.encode()).decode(),
    }
    if sha:
        payload["sha"] = sha

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="PUT",
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            url = result.get("content", {}).get("html_url", "")
            return {
                "ok":  True,
                "url": url,
                "raw": f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}",
            }
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        return {"ok": False, "error": f"PUT error {e.code}: {body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ── DB ────────────────────────────────────────────────────────────────────────

def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Called once at startup."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            task       TEXT    NOT NULL,
            status     TEXT    NOT NULL DEFAULT 'pending',
            output     TEXT,
            worker     TEXT    DEFAULT 'supervisor',
            goal       TEXT,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            goal   TEXT    NOT NULL,
            date   TEXT    NOT NULL DEFAULT (date('now')),
            status TEXT    NOT NULL DEFAULT 'active'
        )
    """)
    conn.commit()
    conn.close()


def add_task(task: str, worker: str = "supervisor", goal: str = "") -> bool:
    """Insert a task. Skips duplicates (same text + pending)."""
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM tasks WHERE task = ? AND status = 'pending'", (task,)
    ).fetchone()
    if existing:
        conn.close()
        return False
    conn.execute(
        "INSERT INTO tasks (task, status, worker, goal) VALUES (?, 'pending', ?, ?)",
        (task, worker, goal),
    )
    conn.commit()
    conn.close()
    return True


def get_pending_tasks_for_worker(worker: str):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'pending' AND worker = ? ORDER BY id LIMIT 1",
        (worker,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_running_count() -> int:
    conn = _get_conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'running'"
    ).fetchone()[0]
    conn.close()
    return n


def get_all_tasks():
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_pending() -> int:
    conn = _get_conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'pending'"
    ).fetchone()[0]
    conn.close()
    return n


def complete_task(task_id: int, output: str = None):
    conn = _get_conn()
    conn.execute(
        "UPDATE tasks SET status = 'done', output = ? WHERE id = ?", (output, task_id)
    )
    conn.commit()
    conn.close()


def fail_task(task_id: int, reason: str = None):
    conn = _get_conn()
    conn.execute(
        "UPDATE tasks SET status = 'failed', output = ? WHERE id = ?", (reason, task_id)
    )
    conn.commit()
    conn.close()


def mark_running(task_id: int):
    conn = _get_conn()
    conn.execute("UPDATE tasks SET status = 'running' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def get_todays_goal():
    conn = _get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT * FROM goals WHERE date = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
        (today,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_goal(goal: str):
    conn = _get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT INTO goals (goal, date, status) VALUES (?, ?, 'active')", (goal, today)
    )
    conn.commit()
    conn.close()

# ── Supervisor ────────────────────────────────────────────────────────────────

def run_supervisor():
    """Picks a daily goal once per day and creates 6 worker tasks."""
    existing = get_todays_goal()
    if existing:
        print(f"📋 Today's goal already set: {existing['goal'][:80]}")
        return existing["goal"]

    print("🧠 Supervisor picking today's goal...")

    prompt = f"""You are a Supervisor AI for an autonomous business agent run by an Indian solo founder.
Today is {datetime.now().strftime('%A, %d %B %Y')}.

Pick ONE ambitious but realistic online business goal for today and break it into exactly 6 tasks.

Available workers:
- research:  finds opportunities, validates ideas, analyzes markets
- builder:   builds HTML pages, writes code, creates files
- marketing: writes copy, social media posts, email campaigns
- outreach:  finds contacts, writes pitches, identifies customers

Rules:
- Goal must be a real online business that could make money in India
- Tasks must be concrete and actionable
- Think: dropshipping, local business digitization, SaaS, content business, affiliate, service business

Reply EXACTLY in this format (no extra text):

GOAL: [one sentence describing today's business goal]
TASKS:
research: [specific research task 1]
research: [specific research task 2]
builder: [specific build task 1]
builder: [specific build task 2]
marketing: [specific marketing task]
outreach: [specific outreach task]
"""

    try:
        result = think(prompt)
    except Exception as e:
        print(f"Supervisor error: {e}")
        return None

    goal = ""
    if "GOAL:" in result:
        goal = result.split("GOAL:")[1].split("\n")[0].strip()
        save_goal(goal)
        print(f"🎯 Today's goal: {goal}")

    if "TASKS:" in result:
        tasks_block = result.split("TASKS:")[1].strip()
        for line in tasks_block.split("\n"):
            line = line.strip()
            if not line:
                continue
            for wtype in WORKER_TYPES:
                if line.lower().startswith(wtype + ":"):
                    task_text = line[len(wtype) + 1:].strip()
                    if task_text:
                        add_task(task_text, worker=wtype, goal=goal)
                        print(f"  ➕ [{wtype}] {task_text[:70]}")
                    break

    # Push today's goal log to GitHub
    log_lines = [
        f"# Daily Goal — {datetime.now().strftime('%d %B %Y')}",
        "",
        f"**Goal:** {goal}",
        "",
        "## Tasks",
    ]
    conn = _get_conn()
    tasks = [dict(r) for r in conn.execute(
        "SELECT * FROM tasks WHERE goal = ?", (goal,)
    ).fetchall()]
    conn.close()
    for t in tasks:
        log_lines.append(f"- [{t['worker']}] {t['task']}")

    push_result = push_to_github(
        f"logs/goal_{datetime.now().strftime('%Y%m%d')}.md",
        "\n".join(log_lines),
        f"supervisor: daily goal {datetime.now().strftime('%Y%m%d')}",
    )
    if push_result["ok"]:
        print(f"  📁 Goal log pushed: {push_result.get('url')}")
    else:
        print(f"  ⚠  Goal log push failed: {push_result.get('error')}")

    return goal

# ── Worker ────────────────────────────────────────────────────────────────────

def _safe_write(filename: str, content: str):
    """Write a file, creating all parent directories first."""
    dirpath = os.path.dirname(filename)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)


def _build_worker_prompt(worker_type: str, task_id: int, task_text: str, goal: str) -> str:
    base = (
        f"You are the {worker_type.upper()} worker agent in an autonomous AI business system.\n"
        f"Overall goal: {goal}\n"
        f"Your task (ID {task_id}): {task_text}\n\n"
    )

    if worker_type == "research":
        return base + f"""Do thorough market research. Find real data, opportunities, competitors, pricing.
Focus on the Indian market. Be specific with numbers, names, and sources.

Reply EXACTLY (no extra text before OUTPUT_FILE):

OUTPUT_FILE: research/research_{task_id}.md
CONTENT:
[Your full research in markdown — headings, bullet points, real data]
"""

    if worker_type == "builder":
        return base + f"""Build a complete, production-ready deliverable.
If it's a landing page: full HTML, dark design, mobile-responsive, Indian market copy, email waitlist form.
If it's code: complete, working, well-commented.

Reply EXACTLY (no extra text before OUTPUT_FILE):

OUTPUT_FILE: builds/output_{task_id}.html
CONTENT:
[Complete HTML starting with <!DOCTYPE html> OR complete code]
"""

    if worker_type == "marketing":
        return base + f"""Write complete, compelling marketing materials.
Include: headline, tagline, social posts (Twitter/LinkedIn/Instagram), email subject lines, WhatsApp message.
Target Indian audience. Use INR pricing. Be specific and punchy.

Reply EXACTLY (no extra text before OUTPUT_FILE):

OUTPUT_FILE: marketing/copy_{task_id}.md
CONTENT:
[All marketing copy in markdown]
"""

    if worker_type == "outreach":
        return base + f"""Find real potential customers, partners, or leads.
Research actual businesses, their contact info, problems they have, and how to pitch them.
Write ready-to-send outreach messages (email + WhatsApp).

Reply EXACTLY (no extra text before OUTPUT_FILE):

OUTPUT_FILE: outreach/leads_{task_id}.md
CONTENT:
[Lead list + outreach messages in markdown]
"""

    return base


def run_worker(worker_type: str):
    """Single worker loop — picks its own tasks and executes them."""
    while True:
        # Respect parallel limit
        while get_running_count() >= MAX_PARALLEL:
            time.sleep(5)

        tasks = get_pending_tasks_for_worker(worker_type)
        if not tasks:
            time.sleep(15)
            continue

        task      = tasks[0]
        task_id   = task["id"]
        task_text = task["task"]
        goal      = task.get("goal", "")

        mark_running(task_id)
        print(f"▶  [{worker_type}] Task {task_id}: {task_text[:70]}")

        prompt = _build_worker_prompt(worker_type, task_id, task_text, goal)

        try:
            result = think(prompt)
        except Exception as e:
            err = str(e)
            if "rate_limit" in err.lower() or "429" in err:
                print(f"  ⏳ Rate limit — waiting 60 s")
                conn = _get_conn()
                conn.execute(
                    "UPDATE tasks SET status = 'pending' WHERE id = ?", (task_id,)
                )
                conn.commit()
                conn.close()
                time.sleep(60)
            else:
                fail_task(task_id, err)
            continue

        file_output = None

        # Save file locally and push to GitHub
        if "OUTPUT_FILE:" in result and "CONTENT:" in result:
            try:
                filename = result.split("OUTPUT_FILE:")[1].split("\n")[0].strip()
                content  = result.split("CONTENT:")[1].strip()

                _safe_write(filename, content)   # creates dirs automatically
                file_output = content

                push_result = push_to_github(
                    filename, content, f"{worker_type}: {task_text[:50]}"
                )
                if push_result["ok"]:
                    url = push_result.get("url", "")
                    print(f"  ✅ Pushed: {url}")
                    file_output = content + f"\n\n---\n✅ GitHub: {url}"
                else:
                    print(f"  ❌ Push failed: {push_result.get('error')}")
                    file_output = content + f"\n\n---\n❌ Push failed: {push_result.get('error')}"

            except Exception as e:
                print(f"  File error: {e}")

        output = file_output or result[:2000]
        complete_task(task_id, output=output)
        print(f"  ✔  [{worker_type}] Done task {task_id}")
        time.sleep(5)

# ── Main entry ────────────────────────────────────────────────────────────────

def run_agent():
    """
    Main entry called by main.py in a daemon thread.
    Starts supervisor + all worker threads.
    """
    time.sleep(2)
    run_supervisor()

    # Start one worker thread per type
    for wtype in WORKER_TYPES:
        t = threading.Thread(target=run_worker, args=(wtype,), daemon=True)
        t.start()
        print(f"🔧 Worker started: {wtype}")
        time.sleep(1)

    # Re-run supervisor every 24 hours for next day's goal
    while True:
        time.sleep(24 * 3600)
        run_supervisor()
