import sqlite3
from brain import think

conn = sqlite3.connect("memory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT
)
""")
conn.commit()

def save(data):
    cursor.execute("INSERT INTO memory (content) VALUES (?)", (data,))
    conn.commit()

def run_agent():
    prompt = """
    1. Plan next useful task
    2. Suggest one online business idea
    3. Break into steps
    4. Give one action to execute now

    Format clearly.
    """

    result = think(prompt)
    save(result)

    return result
