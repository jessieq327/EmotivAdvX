from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from cortex_client import cortex_client

# Create Flask app
app = Flask(__name__)
# Allow all CORS origins for both HTTP and WebSocket
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# HTTP endpoints for fallback polling
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

@app.route("/motion")
def motion():
    return jsonify(cortex_client.get_motion())

# WebSocket: emit brain_data events
@socketio.on('connect')
def on_connect():
    print('Client connected')
    # no blocking here
    socketio.start_background_task(target=publish_loop)


def publish_loop():
    """Continuously send focus+motion to connected clients"""
    while True:
        st = cortex_client.get_status()
        mot = cortex_client.get_motion()
        payload = {
            "type": "met",
            "data": {
                "attention": st["focus_value"],
                "excitement": st.get("excitement")
            }
        }
        socketio.emit('brain_data', payload)
        payload_mot = {
            "type": "mot",
            "data": mot["motion"]
        }
        socketio.emit('brain_data', payload_mot)
        socketio.sleep(0.1)  # 10Hz

if __name__ == '__main__':
    cortex_client.start()
    print("Server running at http://127.0.0.1:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
