import sqlite3
from brain import think

conn = sqlite3.connect("tasks.db", check_same_thread=False)
cursor = conn.cursor()

# Task table
cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT,
    status TEXT
)
""")
conn.commit()

def add_task(task):
    cursor.execute("INSERT INTO tasks (task, status) VALUES (?, ?)", (task, "pending"))
    conn.commit()

def get_tasks():
    cursor.execute("SELECT * FROM tasks")
    return cursor.fetchall()

def complete_task(task_id):
    cursor.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
    conn.commit()

def run_agent():
    tasks = get_tasks()

    prompt = f"""
    You are Deepak AI worker.

    Current tasks:
    {tasks}

    Do:
    1. Create one useful new task
    2. Decide one task to complete
    3. Give action

    Format:
    NEW_TASK: ...
    COMPLETE_TASK_ID: ...
    ACTION: ...
    """

    result = think(prompt)

    # Parse simple execution
    if "NEW_TASK:" in result:
        task = result.split("NEW_TASK:")[1].split("\n")[0].strip()
        add_task(task)

    if "COMPLETE_TASK_ID:" in result:
        try:
            task_id = int(result.split("COMPLETE_TASK_ID:")[1].split("\n")[0].strip())
            complete_task(task_id)
        except:
            pass

    return result
