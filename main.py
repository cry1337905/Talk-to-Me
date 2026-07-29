import os
from math import radians, cos, sin, asin, sqrt
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

active_users = {} 
audio_messages_store = [] # Speichert Audiodaten

def calculate_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    c = 2 * asin(sqrt(a))
    return R * c

@app.route('/update-location', methods=['POST'])
def update_location():
    data = request.get_json()
    user_id = data.get('user_id')
    lat = data.get('lat')
    lon = data.get('lon')

    if user_id and lat is not None and lon is not None:
        active_users[user_id] = {"lat": lat, "lon": lon}
        return jsonify({"status": "ok"}), 200
    return jsonify({"error": "Fehlerhaft"}), 400

@app.route('/send-audio', methods=['POST'])
def send_audio():
    """Empfängt ein Sprach-Audio-Data-URL vom Handy"""
    data = request.get_json()
    user_id = data.get('user_id')
    audio_base64 = data.get('audio') # Das Audiosignal als String
    lat = data.get('lat')
    lon = data.get('lon')

    if not audio_base64 or lat is None or lon is None:
        return jsonify({"error": "Audio oder Standort fehlt"}), 400

    msg_obj = {
        "id": len(audio_messages_store) + 1,
        "user_id": user_id,
        "audio": audio_base64,
        "lat": lat,
        "lon": lon
    }
    audio_messages_store.append(msg_obj)
    
    # Alte Audio-Nachrichten begrenzen, damit der Speicher nicht überläuft
    if len(audio_messages_store) > 50:
        audio_messages_store.pop(0)

    return jsonify({"status": "Gesendet"}), 200

@app.route('/get-nearby-audio', methods=['POST'])
def get_nearby_audio():
    """Holt Audiosignale im 500m Umkreis"""
    data = request.get_json()
    my_lat = data.get('lat')
    my_lon = data.get('lon')
    last_id = data.get('last_id', 0)
    max_radius = 500

    if my_lat is None or my_lon is None:
        return jsonify({"error": "Standort erforderlich"}), 400

    new_messages = []
    for msg in audio_messages_store:
        # Nur neu eingegangene Nachrichten abrufen
        if msg['id'] > last_id:
            dist = calculate_distance_meters(my_lat, my_lon, msg['lat'], msg['lon'])
            if dist <= max_radius:
                new_messages.append({
                    "id": msg['id'],
                    "user_id": msg['user_id'],
                    "audio": msg['audio'],
                    "distance_m": round(dist)
                })

    return jsonify({"messages": new_messages}), 200

@app.route('/', methods=['GET'])
def home():
    return "Talk-to-Me Audio Radius Server läuft!", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)