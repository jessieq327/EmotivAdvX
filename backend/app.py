from flask import Flask, jsonify
from cortex_client import cortex_client

app = Flask(__name__)

@app.route("/status")
def status():
    return jsonify(cortex_client.get_status())

@app.route("/focus")
def focus():
    st = cortex_client.get_status()
    return jsonify({
        "focus": st["focus_value"],
        "age_seconds": st["focus_age_seconds"]
    })

@app.route("/eeg")
def eeg():
    return jsonify(cortex_client.get_eeg())

if __name__ == "__main__":
    cortex_client.start()
    print("Server: http://127.0.0.1:5000")
    app.run(debug=True)
