"""
agent.py — Autonomous AI agent with GitHub push capability
"""

import sqlite3
import os
import json
import base64
import urllib.request
import urllib.error
import time
from brain import think

DB_PATH     = os.getenv("DB_PATH", "tasks.db")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO  = os.getenv("GITHUB_REPO", "")


# ── GitHub helper ─────────────────────────────────────────────────────────────

def push_to_github(filename: str, content: str, commit_msg: str = None) -> dict:
    """Push a file to the GitHub repo via API. Returns {ok, url, error}."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return {"ok": False, "error": "GITHUB_TOKEN or GITHUB_REPO not set"}

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "deepak-ai-agent"
    }

    # Check if file exists (to get sha for update)
    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            existing = json.loads(resp.read())
            sha = existing.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return {"ok": False, "error": f"GitHub GET error: {e.code}"}

    # Build payload
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    payload = {
        "message": commit_msg or f"agent: add {filename}",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(api_url, data=data, headers=headers, method="PUT")
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            html_url = result.get("content", {}).get("html_url", "")
            raw_url  = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}"
            pages_url = f"https://{GITHUB_REPO.split('/')[0]}.github.io/{GITHUB_REPO.split('/')[1]}/{filename}"
            return {"ok": True, "url": html_url, "raw": raw_url, "pages": pages_url}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"ok": False, "error": f"GitHub PUT error {e.code}: {body[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── DB setup ──────────────────────────────────────────────────────────────────

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
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def add_task(task: str) -> bool:
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM tasks WHERE task = ? AND status = 'pending'", (task,)
    ).fetchone()
    if existing:
        conn.close()
        return False
    conn.execute("INSERT INTO tasks (task, status) VALUES (?, 'pending')", (task,))
    conn.commit()
    conn.close()
    return True


def get_tasks():
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'pending' ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
        "UPDATE tasks SET status = 'done', output = ? WHERE id = ?",
        (output, task_id)
    )
    conn.commit()
    conn.close()


def fail_task(task_id: int, reason: str = None):
    conn = _get_conn()
    conn.execute(
        "UPDATE tasks SET status = 'failed', output = ? WHERE id = ?",
        (reason, task_id)
    )
    conn.commit()
    conn.close()


# ── Phase detection ───────────────────────────────────────────────────────────

def detect_phase(task_text: str) -> str:
    t = task_text.lower()
    if any(k in t for k in ["build html", "create html", "generate html", "write html", "landing page", "webpage", "website"]):
        return "build"
    if any(k in t for k in ["push to github", "deploy", "upload to github"]):
        return "deploy"
    return "research"


# ── Agent prompts ─────────────────────────────────────────────────────────────

def research_prompt(task_id, task_text):
    return f"""You are an autonomous AI agent for an Indian solo founder.

Current task (ID {task_id}): {task_text}

Do thorough research and produce useful output. Then:
1. Pick the SINGLE BEST micro-SaaS idea from your research
2. Queue the next step: building an HTML landing page for that idea

Reply EXACTLY in this format:

NEW_TASK: Build HTML landing page for [your chosen idea name] — a [one line description]
COMPLETE_TASK_ID: {task_id}
ACTION: Researched and selected best micro-SaaS idea

OUTPUT_FILE: research.txt
CONTENT:
[Your full research output here. Include the chosen idea clearly at the top.]
"""


def build_prompt(task_id, task_text):
    return f"""You are an expert web developer and copywriter.

Task (ID {task_id}): {task_text}

Build a complete, beautiful, single-file HTML landing page for this micro-SaaS product.

Requirements:
- Fully self-contained HTML (no external dependencies except Google Fonts CDN)
- Modern dark design with gradient hero section
- Sections: Hero, Problem, Solution, Features (3), Pricing (2 tiers), FAQ (3), Footer
- Compelling Indian market focused copy
- Mobile responsive
- Email waitlist form (no backend needed, just UI)
- Professional and investor-ready

Reply EXACTLY in this format:

NEW_TASK: Push index.html to GitHub for [idea name]
COMPLETE_TASK_ID: {task_id}
ACTION: Built complete HTML landing page

OUTPUT_FILE: index.html
CONTENT:
[Your complete HTML here — must start with <!DOCTYPE html>]
"""


def deploy_prompt(task_id, task_text):
    return f"""Task (ID {task_id}): {task_text}

The HTML file has been pushed to GitHub successfully.

Reply EXACTLY in this format:

NEW_TASK: NONE
COMPLETE_TASK_ID: {task_id}
ACTION: Confirmed deployment to GitHub

OUTPUT_FILE: deployment.txt
CONTENT:
Deployment complete. The landing page has been pushed to GitHub.
Next steps:
1. Enable GitHub Pages: repo Settings → Pages → Branch: main → Save
2. Your site will be live at: https://{GITHUB_REPO.split('/')[0]}.github.io/{GITHUB_REPO.split('/')[1]}/
3. Share the link and start collecting waitlist signups
"""


# ── Main agent loop ───────────────────────────────────────────────────────────

def run_agent():
    while True:
        tasks = get_tasks()

        if not tasks:
            time.sleep(10)
            continue

        current   = tasks[0]
        task_id   = current["id"]
        task_text = current["task"]
        phase     = detect_phase(task_text)

        # Mark running
        conn = _get_conn()
        conn.execute("UPDATE tasks SET status = 'running' WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()

        print(f"▶ Task {task_id} [{phase}]: {task_text[:60]}")

        # Pick prompt by phase
        if phase == "build":
            prompt = build_prompt(task_id, task_text)
        elif phase == "deploy":
            prompt = deploy_prompt(task_id, task_text)
        else:
            prompt = research_prompt(task_id, task_text)

        # Call LLM
        try:
            result = think(prompt)
        except Exception as e:
            fail_task(task_id, str(e))
            time.sleep(5)
            continue

        # Parse NEW_TASK
        new_task_text = None
        if "NEW_TASK:" in result:
            try:
                new_task_text = result.split("NEW_TASK:")[1].split("\n")[0].strip()
                if new_task_text and new_task_text.upper() != "NONE":
                    add_task(new_task_text)
                    print(f"  ➕ Queued: {new_task_text[:60]}")
                else:
                    new_task_text = None
            except Exception:
                pass

        # Parse OUTPUT_FILE + CONTENT
        file_output  = None
        pushed_url   = None

        if "OUTPUT_FILE:" in result and "CONTENT:" in result:
            try:
                filename = result.split("OUTPUT_FILE:")[1].split("\n")[0].strip()
                content  = result.split("CONTENT:")[1].strip()

                # Save locally
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"  💾 Saved: {filename}")
                file_output = content

                # Push HTML files to GitHub automatically
                if filename.endswith(".html"):
                    print(f"  🚀 Pushing {filename} to GitHub...")
                    push_result = push_to_github(
                        filename,
                        content,
                        f"agent: auto-deploy {filename}"
                    )
                    if push_result["ok"]:
                        pushed_url = push_result.get("url", "")
                        print(f"  ✅ Pushed! {pushed_url}")
                        file_output = content + f"\n\n---\n✅ Pushed to GitHub: {pushed_url}"
                        # Queue deploy confirmation
                        add_task(f"Push to GitHub complete — enable GitHub Pages to go live")
                    else:
                        err = push_result.get("error", "unknown")
                        print(f"  ❌ Push failed: {err}")
                        file_output = content + f"\n\n---\n❌ GitHub push failed: {err}"

            except Exception as e:
                print(f"  File error: {e}")

        # Complete task
        if "COMPLETE_TASK_ID:" in result:
            try:
                done_id = int(result.split("COMPLETE_TASK_ID:")[1].split("\n")[0].strip())
                complete_task(done_id, output=file_output or result[:1000])
            except Exception:
                complete_task(task_id, output=file_output or result[:1000])
        else:
            complete_task(task_id, output=file_output or result[:1000])

        print(f"  ✔ Done task {task_id}")
        time.sleep(3)
