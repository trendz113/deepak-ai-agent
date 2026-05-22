"""
main.py — Flask server for Deepak AI Agent
Starts the agent loop in a background thread on startup.
"""

import os
import threading
from flask import Flask, jsonify, request
import agent

app = Flask(__name__)

# ── Start agent loop in background ──────────────
def _start_agent():
    agent.init_db()
    # Seed a first task if DB is empty
    if agent.count_pending() == 0:
        agent.add_task("Research 3 profitable micro-SaaS ideas for Indian solo founders in 2025")

_start_agent()
_thread = threading.Thread(target=agent.run_agent, daemon=True)
_thread.start()

# ── Routes ───────────────────────────────────────

@app.route("/")
def home():
    pending = agent.count_pending()
    return jsonify({
        "status": "running",
        "pending_tasks": pending,
        "message": "Deepak AI Agent is alive 🚀"
    })

@app.route("/tasks")
def tasks():
    return jsonify(agent.get_all_tasks())

@app.route("/command", methods=["POST"])
def command():
    """Add a task manually via POST { "task": "..." }"""
    data = request.get_json(silent=True) or {}
    task_text = data.get("task", "").strip()
    if not task_text:
        return jsonify({"error": "task field is required"}), 400
    added = agent.add_task(task_text)
    return jsonify({
        "queued": added,
        "task": task_text,
        "message": "Added" if added else "Already exists"
    })

@app.route("/chat")
def chat_ui():
    """Mobile-friendly chat interface with expandable full output."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Deepak AI Agent</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, sans-serif; background: #0f0f0f; color: #f0f0f0; }
  header { background: #1a1a1a; padding: 16px; text-align: center; border-bottom: 1px solid #333; }
  header h1 { font-size: 18px; font-weight: 600; }
  header p  { font-size: 12px; color: #888; margin-top: 4px; }
  #tasks { padding: 16px; padding-bottom: 80px; overflow-y: auto; }
  .task-card {
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px;
    padding: 12px 14px; margin-bottom: 10px; cursor: pointer;
    transition: border-color 0.2s;
  }
  .task-card:hover { border-color: #444; }
  .task-card.expanded { border-color: #2563eb; }
  .task-desc { font-size: 14px; line-height: 1.5; font-weight: 500; }
  .task-meta { font-size: 11px; color: #666; margin-top: 6px; display: flex; gap: 10px; align-items: center; }
  .badge { padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 500; }
  .badge.done    { background: #0d3d1f; color: #4ade80; }
  .badge.pending { background: #1e3a5f; color: #60a5fa; }
  .badge.running { background: #3d2b00; color: #fbbf24; }
  .badge.failed  { background: #3d0d0d; color: #f87171; }
  .task-output {
    display: none; margin-top: 12px; padding-top: 12px;
    border-top: 1px solid #2a2a2a; font-size: 13px; color: #ccc;
    line-height: 1.7; white-space: pre-wrap; word-break: break-word;
  }
  .task-card.expanded .task-output { display: block; }
  .toggle-hint { font-size: 11px; color: #555; margin-left: auto; }
  .copy-btn {
    font-size: 11px; color: #888; background: #2a2a2a; border: 1px solid #3a3a3a;
    border-radius: 6px; padding: 3px 10px; cursor: pointer; margin-top: 10px;
    display: inline-block;
  }
  .copy-btn:hover { background: #333; color: #fff; }
  footer { position: fixed; bottom: 0; left: 0; right: 0; background: #1a1a1a;
           padding: 12px 16px; border-top: 1px solid #333; display: flex; gap: 8px; }
  input  { flex: 1; background: #2a2a2a; border: 1px solid #444; border-radius: 8px;
           padding: 10px 14px; color: #f0f0f0; font-size: 14px; outline: none; }
  button.send-btn { background: #2563eb; color: white; border: none; border-radius: 8px;
           padding: 10px 18px; font-size: 14px; cursor: pointer; }
</style>
</head>
<body>
<header><h1>⚡ Deepak AI Agent</h1><p id="status">Loading...</p></header>
<div id="tasks"><p style="color:#666;text-align:center;padding:40px 0">Loading tasks…</p></div>
<footer>
  <input id="inp" type="text" placeholder="Give a task to the agent…" />
  <button class="send-btn" onclick="send()">Send</button>
</footer>
<script>
let expandedIds = new Set();

function toggle(id, e) {
  e.stopPropagation();
  const card = document.getElementById('card-' + id);
  if (!card) return;
  if (expandedIds.has(id)) {
    expandedIds.delete(id);
    card.classList.remove('expanded');
    card.querySelector('.toggle-hint').textContent = 'tap to expand';
  } else {
    expandedIds.add(id);
    card.classList.add('expanded');
    card.querySelector('.toggle-hint').textContent = 'tap to collapse';
  }
}

function copyOutput(id, e) {
  e.stopPropagation();
  const el = document.getElementById('output-' + id);
  if (!el) return;
  navigator.clipboard.writeText(el.innerText).then(() => {
    const btn = document.getElementById('copy-' + id);
    if (btn) { btn.textContent = '✓ Copied'; setTimeout(() => btn.textContent = '⎘ Copy output', 1500); }
  });
}

function formatOutput(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\\*\\*(.+?)\\*\\*/g, '<strong style="color:#fff">$1</strong>');
}

async function load() {
  try {
    const r = await fetch('/tasks');
    const tasks = await r.json();
    const pending = tasks.filter(t => t.status === 'pending').length;
    document.getElementById('status').textContent =
      tasks.length + ' tasks · ' + pending + ' pending';
    document.getElementById('tasks').innerHTML = tasks.length
      ? tasks.map(t => {
          const isExp = expandedIds.has(t.id);
          const hasOutput = t.output && t.output.trim().length > 0;
          return `
          <div class="task-card ${isExp ? 'expanded' : ''}" id="card-${t.id}" onclick="toggle(${t.id}, event)">
            <div class="task-desc">${t.task.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>
            <div class="task-meta">
              <span class="badge ${t.status}">${t.status}</span>
              <span>${(t.created_at||'').slice(0,16).replace('T',' ')}</span>
              ${hasOutput ? `<span class="toggle-hint">${isExp ? 'tap to collapse' : 'tap to expand'}</span>` : ''}
            </div>
            ${hasOutput ? `
            <div class="task-output" id="output-${t.id}">${formatOutput(t.output)}
<button class="copy-btn" id="copy-${t.id}" onclick="copyOutput(${t.id}, event)">⎘ Copy output</button>
            </div>` : ''}
          </div>`;
        }).join('')
      : '<p style="color:#666;text-align:center;padding:40px 0">No tasks yet.</p>';
  } catch(e) {
    document.getElementById('status').textContent = 'Error loading tasks';
  }
}

async function send() {
  const inp = document.getElementById('inp');
  const task = inp.value.trim();
  if (!task) return;
  inp.value = '';
  await fetch('/command', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task })
  });
  load();
}

document.getElementById('inp').addEventListener('keypress', e => {
  if (e.key === 'Enter') send();
});

load();
setInterval(load, 15000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
