from flask import Flask, jsonify
import threading
import time
from agent import run_agent

app = Flask(__name__)

latest = "Starting..."

def loop():
    global latest
    while True:
        try:
            latest = run_agent()
            print("AI:", latest)
        except Exception as e:
            latest = f"ERROR: {str(e)}"
            print("ERROR:", e)

        time.sleep(120)

@app.route("/")
def home():
    return jsonify({"AI": latest})

# Run loop safely in background
threading.Thread(target=loop, daemon=True).start()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
