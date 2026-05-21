from flask import Flask, request, jsonify
import threading
import time
from agent import run_agent
from brain import think

app = Flask(__name__)

latest = "Starting..."

# 🔁 Autonomous loop
def loop():
    global latest
    while True:
        latest = run_agent()
        time.sleep(120)

# 📱 Check AI
@app.route("/")
def home():
    return jsonify({"AI": latest})

# 📱 Send command
@app.route("/command", methods=["POST"])
def command():
    data = request.json
    user_input = data.get("text")

    response = think(user_input)

    return jsonify({"response": response})

# start loop
threading.Thread(target=loop).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
