from flask import Flask, Response, request, jsonify
import threading
import time
import os
from agent import run_agent
from brain import think

app = Flask(__name__)

latest = "Starting..."

# 🔁 Background AI loop
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

# 📱 Clean text output (browser)
@app.route("/")
def home():
    return Response(latest, mimetype='text/plain')

# 📱 Command API (optional)
@app.route("/command", methods=["POST"])
def command():
    data = request.json
    user_input = data.get("text", "")

    response = think(user_input)

    return jsonify({"response": response})

@app.route("/tasks")
def tasks():
    from agent import get_tasks
    return jsonify(get_tasks())

# Start background thread safely
threading.Thread(target=loop, daemon=True).start()

# Run server (Railway compatible)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
