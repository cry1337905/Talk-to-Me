import os
from math import radians, cos, sin, asin, sqrt
from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Speichert { socket_id: {"peer_id": ..., "lat": ..., "lon": ...} }
peers = {}

def calculate_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    return R * 2 * asin(sqrt(a))

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in peers:
        del peers[request.sid]

@socketio.on('register_peer')
def handle_register(data):
    """Handy übermittelt seine Peer-ID für direkte Sprachverbindung und seinen Standort"""
    peer_id = data.get('peer_id')
    lat = data.get('lat')
    lon = data.get('lon')
    
    peers[request.sid] = {"peer_id": peer_id, "lat": lat, "lon": lon}
    
    # Prücke für alle Kontakte im 500m Umkreis
    nearby_peers = []
    for sid, info in peers.items():
        if sid != request.sid and info['lat'] is not None:
            dist = calculate_distance_meters(lat, lon, info['lat'], info['lon'])
            if dist <= 500:
                nearby_peers.append(info['peer_id'])
    
    # Schicke dem Handy die Liste der erreichbaren Funker in der Nähe
    emit('connect_to_peers', {'peers': nearby_peers})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)