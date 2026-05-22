""" 
agent.py — Supervisor + Worker Agent System
Supervisor picks daily goals, breaks into tasks, assigns to specialist workers.
Workers run 2-3 in parallel. Results pushed to GitHub + emailed.
"""

import sqlite3
import os
import json
import base64
import urllib.request
import urllib.error
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from brain import think

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH       = os.getenv("DB_PATH", "tasks.db")
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO   = os.getenv("GITHUB_REPO", "")
SMTP_EMAIL    = os.getenv("SMTP_EMAIL", "")       # your Gmail
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")    # Gmail app password
REPORT_EMAIL  = "tremendouscollections@gmail.com"

WORKER_TYPES = ["research", "builder", "marketing", "outreach"]


# ── GitHub ────────────────────────────────────────────────────────────────────
def push_to_github(filename: str, content: str, commit_msg: str = None) -> dict:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return {"ok": False, "error": "GITHUB_TOKEN or GITHUB_REPO not set"}
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "deepak-ai-agent"
    }
    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            sha = json.loads(resp.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return {"ok": False, "error": f"GET error {e.code}"}
    payload = {"message": commit_msg or f"agent: {filename}", "content": base64.b64encode(content.encode()).decode()}
    if sha:
        payload["sha"] = sha
    try:
        req = urllib.request.Request(api_url, data=json.dumps(payload).encode(), headers=headers, method="PUT")
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            url = result.get("content", {}).get("html_url", "")
            return {"ok": True, "url": url, "raw": f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}"}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"PUT error {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Email ─────────────────────────────────────────────────────────────────────
def send_email(subject: str, body: str):
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("⚠ Email not configured (SMTP_EMAIL / SMTP_PASSWORD missing)")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_EMAIL
        msg["To"]      = REPORT_EMAIL
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(SMTP_EMAIL, SMTP_PASSWORD)
            s.sendmail(SMTP_EMAIL, REPORT_EMAIL, msg.as_string())
        print(f"✉ Email sent: {subject}")
        return True
    except Exception as e:
        print(f"✉ Email failed: {e}")
        return False


def build_report_email(goal: str, tasks: list) -> tuple:
    done    = [t for t in tasks if t["status"] == "done"]
    failed  = [t for t in tasks if t["status"] == "failed"]
    running = [t for t in tasks if t["status"] == "running"]
    pending = [t for t in tasks if t["status"] == "pending"]

    github_links = []
    for t in done:
        if t.get("output") and "github.com" in (t.get("output") or ""):
            for word in (t.get("output") or "").split():
                if word.startswith("https://github.com"):
                    github_links.append(word.strip(".,)>"))

    subject = f"🤖 Deepak Agent Report — {datetime.now().strftime('%d %b %Y %H:%M')}"

    rows = ""
    for t in tasks:
        color = {"done": "#4ade80", "failed": "#f87171", "running": "#fbbf24", "pending": "#60a5fa"}.get(t["status"], "#aaa")
        output_preview = (t.get("output") or "")[:300].replace("<", "&lt;").replace(">", "&gt;")
        rows += f"""
        <tr>
          <td style='padding:8px;border-bottom:1px solid #2a2a2a;color:#aaa;font-size:12px'>{t['id']}</td>
          <td style='padding:8px;border-bottom:1px solid #2a2a2a;font-size:13px'>{t['task'][:80]}</td>
          <td style='padding:8px;border-bottom:1px solid #2a2a2a'><span style='background:#1a1a1a;color:{color};padding:2px 8px;border-radius:20px;font-size:11px'>{t['status']}</span></td>
          <td style='padding:8px;border-bottom:1px solid #2a2a2a;color:#888;font-size:11px'>{t.get('worker','—')}</td>
          <td style='padding:8px;border-bottom:1px solid #2a2a2a;color:#aaa;font-size:11px'>{output_preview}{'…' if len(t.get('output') or '') > 300 else ''}</td>
        </tr>"""

    links_html = ""
    if github_links:
        links_html = "<h3 style='color:#60a5fa'>📁 GitHub Files</h3><ul>" + "".join(f"<li><a href='{l}' style='color:#60a5fa'>{l}</a></li>" for l in set(github_links)) + "</ul>"

    body = f"""
    <div style='background:#0f0f0f;color:#f0f0f0;font-family:-apple-system,sans-serif;padding:24px;max-width:800px'>
      <h1 style='color:#fff;font-size:20px'>⚡ Deepak AI Agent — Daily Report</h1>
      <p style='color:#888'>{datetime.now().strftime('%A, %d %B %Y at %H:%M')}</p>

      <h2 style='color:#fff;font-size:16px;margin-top:24px'>🎯 Today's Goal</h2>
      <p style='background:#1a1a1a;padding:12px;border-radius:8px;color:#f0f0f0'>{goal}</p>

      <h2 style='color:#fff;font-size:16px;margin-top:24px'>📊 Summary</h2>
      <div style='display:flex;gap:12px;flex-wrap:wrap'>
        <div style='background:#1a1a1a;padding:12px 20px;border-radius:8px;text-align:center'><div style='font-size:24px;color:#4ade80'>{len(done)}</div><div style='font-size:12px;color:#888'>Done</div></div>
        <div style='background:#1a1a1a;padding:12px 20px;border-radius:8px;text-align:center'><div style='font-size:24px;color:#fbbf24'>{len(running)}</div><div style='font-size:12px;color:#888'>Running</div></div>
        <div style='background:#1a1a1a;padding:12px 20px;border-radius:8px;text-align:center'><div style='font-size:24px;color:#60a5fa'>{len(pending)}</div><div style='font-size:12px;color:#888'>Pending</div></div>
        <div style='background:#1a1a1a;padding:12px 20px;border-radius:8px;text-align:center'><div style='font-size:24px;color:#f87171'>{len(failed)}</div><div style='font-size:12px;color:#888'>Failed</div></div>
      </div>

      {links_html}

      <h2 style='color:#fff;font-size:16px;margin-top:24px'>📋 All Tasks</h2>
      <table style='width:100%;border-collapse:collapse;background:#1a1a1a;border-radius:8px'>
        <tr style='background:#2a2a2a'>
          <th style='padding:8px;text-align:left;color:#888;font-size:12px'>ID</th>
          <th style='padding:8px;text-align:left;color:#888;font-size:12px'>Task</th>
          <th style='padding:8px;text-align:left;color:#888;font-size:12px'>Status</th>
          <th style='padding:8px;text-align:left;color:#888;font-size:12px'>Worker</th>
          <th style='padding:8px;text-align:left;color:#888;font-size:12px'>Output Preview</th>
        </tr>
        {rows}
      </table>

      <p style='color:#555;font-size:11px;margin-top:24px'>Deepak AI Agent — running on Railway · {GITHUB_REPO}</p>
    </div>"""

    return subject, body


# ── DB ────────────────────────────────────────────────────────────────────────
def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
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
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            goal       TEXT    NOT NULL,
            date       TEXT    NOT NULL DEFAULT (date('now')),
            status     TEXT    NOT NULL DEFAULT 'active'
        )
    """)
    conn.commit()
    conn.close()


def add_task(task: str, worker: str = "supervisor", goal: str = "") -> bool:
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM tasks WHERE task = ? AND status = 'pending'", (task,)
    ).fetchone()
    if existing:
        conn.close()
        return False
    conn.execute(
        "INSERT INTO tasks (task, status, worker, goal) VALUES (?, 'pending', ?, ?)",
        (task, worker, goal)
    )
    conn.commit()
    conn.close()
    return True


def get_pending_tasks_for_worker(worker: str):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'pending' AND worker = ? ORDER BY id LIMIT 1",
        (worker,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_running_count():
    conn = _get_conn()
    n = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'running'").fetchone()[0]
    conn.close()
    return n


def get_all_tasks():
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_pending() -> int:
    conn = _get_conn()
    n = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'").fetchone()[0]
    conn.close()
    return n


def complete_task(task_id: int, output: str = None):
    conn = _get_conn()
    conn.execute("UPDATE tasks SET status = 'done', output = ? WHERE id = ?", (output, task_id))
    conn.commit()
    conn.close()


def fail_task(task_id: int, reason: str = None):
    conn = _get_conn()
    conn.execute("UPDATE tasks SET status = 'failed', output = ? WHERE id = ?", (reason, task_id))
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
        (today,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_goal(goal: str):
    conn = _get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute("INSERT INTO goals (goal, date, status) VALUES (?, ?, 'active')", (goal, today))
    conn.commit()
    conn.close()


# ── Supervisor ────────────────────────────────────────────────────────────────
def run_supervisor():
    """Supervisor picks a daily goal and breaks it into worker tasks."""
    existing = get_todays_goal()
    if existing:
        print(f"📋 Today's goal already set: {existing['goal'][:60]}")
        return existing["goal"]

    print("🧠 Supervisor picking today's goal...")
    prompt = f"""You are a Supervisor AI for an autonomous business agent run by an Indian solo founder.

Today is {datetime.now().strftime('%A, %d %B %Y')}.

Your job: pick ONE ambitious but realistic online business goal for today and break it into exactly 6 tasks — one per worker type, some workers get 2 tasks.

Available workers:
- research: finds opportunities, validates ideas, analyzes markets
- builder: builds HTML pages, writes code, creates files
- marketing: writes copy, social media posts, email campaigns
- outreach: finds contacts, writes pitches, identifies customers

Rules:
- Goal must be a real online business that could make money in India
- Tasks must be concrete and actionable
- Each task must clearly say which worker should do it
- Think: dropshipping, local business digitization, SaaS, content business, affiliate, service business

Reply EXACTLY in this format:

GOAL: [one sentence describing today's business goal]

TASKS:
research: [specific research task 1]
research: [specific research task 2]
builder: [specific build task]
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
                    task_text = line[len(wtype)+1:].strip()
                    if task_text:
                        add_task(task_text, worker=wtype, goal=goal)
                        print(f"  ➕ [{wtype}] {task_text[:60]}")
                    break

    # Push goal to GitHub as daily log
    log = f"# Daily Goal — {datetime.now().strftime('%d %B %Y')}\n\n**Goal:** {goal}\n\n## Tasks\n"
    conn = _get_conn()
    tasks = [dict(r) for r in conn.execute("SELECT * FROM tasks WHERE goal = ?", (goal,)).fetchall()]
    conn.close()
    for t in tasks:
        log += f"- [{t['worker']}] {t['task']}\n"
    push_to_github(f"logs/goal_{datetime.now().strftime('%Y%m%d')}.md", log, f"supervisor: daily goal {datetime.now().strftime('%Y%m%d')}")

    return goal


# ── Worker ────────────────────────────────────────────────────────────────────
def run_worker(worker_type: str):
    """Single worker loop — picks its own tasks and executes them."""
    while True:
        # Respect parallel limit (max 3 running at once)
        while get_running_count() >= 3:
            time.sleep(5)

        tasks = get_pending_tasks_for_worker(worker_type)
        if not tasks:
            time.sleep(15)
            continue

        task   = tasks[0]
        task_id   = task["id"]
        task_text = task["task"]
        goal      = task.get("goal", "")

        mark_running(task_id)
        print(f"▶ [{worker_type}] Task {task_id}: {task_text[:60]}")

        prompt = build_worker_prompt(worker_type, task_id, task_text, goal)

        try:
            result = think(prompt)
        except Exception as e:
            err = str(e)
            if "rate_limit" in err.lower() or "429" in err:
                print(f"  ⏳ Rate limit — waiting 60s")
                # Put back to pending
                conn = _get_conn()
                conn.execute("UPDATE tasks SET status = 'pending' WHERE id = ?", (task_id,))
                conn.commit()
                conn.close()
                time.sleep(60)
            else:
                fail_task(task_id, err)
            continue

        file_output = None

        # Save + push files
        if "OUTPUT_FILE:" in result and "CONTENT:" in result:
            try:
                filename = result.split("OUTPUT_FILE:")[1].split("\n")[0].strip()
                content  = result.split("CONTENT:")[1].strip()
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                file_output = content
                push_result = push_to_github(filename, content, f"{worker_type}: {task_text[:50]}")
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
        print(f"  ✔ [{worker_type}] Done task {task_id}")
        time.sleep(5)


def build_worker_prompt(worker_type: str, task_id: int, task_text: str, goal: str) -> str:
    base = f"""You are the {worker_type.upper()} worker agent in an autonomous AI business system.

Overall goal: {goal}
Your task (ID {task_id}): {task_text}

"""
    if worker_type == "research":
        return base + """Do thorough market research. Find real data, opportunities, competitors, pricing.
Focus on Indian market. Be specific with numbers and names.

Reply EXACTLY:
OUTPUT_FILE: research/research_{task_id}.md
CONTENT:
[Your full research in markdown — headings, bullet points, real data]
"""
    elif worker_type == "builder":
        return base + """Build a complete, production-ready deliverable.
If it's a landing page: full HTML, dark design, mobile responsive, Indian market copy, email waitlist form.
If it's code: complete, working, well commented.

Reply EXACTLY:
OUTPUT_FILE: builds/output_{task_id}.html
CONTENT:
[Complete HTML starting with <!DOCTYPE html> OR complete code]
"""
    elif worker_type == "marketing":
        return base + """Write complete, compelling marketing materials.
Include: headline, tagline, social posts (Twitter/LinkedIn/Instagram), email subject lines, WhatsApp message.
Target Indian audience. Use INR pricing. Be specific.

Reply EXACTLY:
OUTPUT_FILE: marketing/copy_{task_id}.md
CONTENT:
[All marketing copy in markdown]
"""
    elif worker_type == "outreach":
        return base + """Find real potential customers, partners, or leads.
Research actual businesses, their contact info, what problems they have, how to pitch them.
Write ready-to-send outreach messages (email + WhatsApp).

Reply EXACTLY:
OUTPUT_FILE: outreach/leads_{task_id}.md
CONTENT:
[Lead list + outreach messages in markdown]
"""
    return base


# ── Daily report emailer ──────────────────────────────────────────────────────
def run_daily_reporter():
    """Sends an email report every 6 hours with full task status."""
    while True:
        time.sleep(6 * 3600)  # every 6 hours
        print("📧 Sending report email...")
        goal_row = get_todays_goal()
        goal = goal_row["goal"] if goal_row else "No goal set today"
        tasks = get_all_tasks()
        subject, body = build_report_email(goal, tasks)
        send_email(subject, body)


# ── Main entry ────────────────────────────────────────────────────────────────
def run_agent():
    """
    Main entry called by main.py in a daemon thread.
    Starts supervisor + all worker threads + reporter.
    """
    # Run supervisor once at startup (picks today's goal)
    time.sleep(2)
    run_supervisor()

    # Start worker threads (2-3 in parallel)
    for wtype in WORKER_TYPES:
        t = threading.Thread(target=run_worker, args=(wtype,), daemon=True)
        t.start()
        print(f"🔧 Worker started: {wtype}")
        time.sleep(2)

    # Start daily reporter
    reporter = threading.Thread(target=run_daily_reporter, daemon=True)
    reporter.start()

    # Re-run supervisor every 24 hours for next day's goal
    while True:
        time.sleep(24 * 3600)
        run_supervisor()
