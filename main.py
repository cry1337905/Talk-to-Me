import os
from math import radians, cos, sin, asin, sqrt
from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# In-Memory Speicher für Live-Positionen der verbundenen Nutzer
users = {} # { socket_id: {"lat": 0.0, "lon": 0.0} }

def calculate_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    return R * 2 * asin(sqrt(a))

@socketio.on('connect')
def handle_connect():
    print(f"Client verbunden: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in users:
        del users[request.sid]
    print(f"Client getrennt: {request.sid}")

@socketio.on('update_location')
def handle_location(data):
    """Speichert den aktuellen Standort des Handys"""
    users[request.sid] = {
        "lat": data.get('lat'),
        "lon": data.get('lon')
    }

@socketio.on('audio_stream')
def handle_audio_stream(stream_data):
    """Nimmt Live-Audio-Happen entgegen und verteilt sie an Handys im 500m Radius"""
    sender = users.get(request.sid)
    if not sender or sender['lat'] is None:
        return

    # Sende das Audio-Signal NUR an Nutzer im 500m-Umkreis
    for target_sid, target_data in users.items():
        if target_sid != request.sid and target_data['lat'] is not None:
            dist = calculate_distance_meters(sender['lat'], sender['lon'], target_data['lat'], target_data['lon'])
            if dist <= 500: # 500 Meter Radius
                emit('live_audio', {
                    'sender_id': request.sid[:5],
                    'stream': stream_data,
                    'distance': round(dist)
                }, room=target_sid)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)