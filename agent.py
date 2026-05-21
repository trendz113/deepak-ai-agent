import sqlite3
from brain import think

# Database connection
conn = sqlite3.connect("tasks.db", check_same_thread=False)
cursor = conn.cursor()

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT,
    status TEXT
)
""")
conn.commit()

# ➕ Add task
def add_task(task):
    cursor.execute("INSERT INTO tasks (task, status) VALUES (?, ?)", (task, "pending"))
    conn.commit()

# 📋 Get tasks
def get_tasks():
    cursor.execute("SELECT * FROM tasks")
    return cursor.fetchall()

# ✅ Complete task
def complete_task(task_id):
    cursor.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
    conn.commit()

# 🤖 MAIN AI WORKER
def run_agent():
    tasks = get_tasks()

    prompt = f"""
You are Deepak AI worker.

Current tasks:
{tasks}

Now DO REAL WORK:

If task is about research or business:
→ generate actual useful output

Do:
1. Create one useful new task
2. Complete one task
3. Execute it

Format EXACTLY:

NEW_TASK: ...
COMPLETE_TASK_ID: ...
ACTION: ...

OUTPUT_FILE: filename.txt
CONTENT:
(write real useful content here)
"""

    result = think(prompt)

    # ➕ Add new task
    if "NEW_TASK:" in result:
        try:
            task = result.split("NEW_TASK:")[1].split("\n")[0].strip()
            add_task(task)
        except:
            pass

    # ✅ Complete task
    if "COMPLETE_TASK_ID:" in result:
        try:
            task_id = int(result.split("COMPLETE_TASK_ID:")[1].split("\n")[0].strip())
            complete_task(task_id)
        except:
            pass

    # 📄 Create file (REAL EXECUTION)
    if "OUTPUT_FILE:" in result and "CONTENT:" in result:
        try:
            filename = result.split("OUTPUT_FILE:")[1].split("\n")[0].strip()
            content = result.split("CONTENT:")[1].strip()

            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"✅ File created: {filename}")

        except Exception as e:
            print("File error:", e)

    return result
