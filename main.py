import os
from math import radians, cos, sin, asin, sqrt
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# In-Memory-Speicher für aktive Nutzer und Nachrichten (für die Produktion wäre eine DB wie PostgreSQL besser)
active_users = {} # { user_id: {"lat": ..., "lon": ...} }
messages_store = [] # [{"user_id": ..., "lat": ..., "lon": ..., "text": ...}]

def calculate_distance_meters(lat1, lon1, lat2, lon2):
    """Berechnet die Entfernung zwischen zwei GPS-Punkten in Metern (Haversine-Formel)"""
    R = 6371000  # Erdradius in Metern
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    c = 2 * asin(sqrt(a))
    return R * c

@app.route('/update-location', methods=['POST'])
def update_location():
    """Handy sendet seine GPS-Daten an den Server"""
    data = request.get_json()
    user_id = data.get('user_id')
    lat = data.get('lat')
    lon = data.get('lon')

    if not user_id or lat is None or lon is None:
        return jsonify({"error": "Ungültige Daten"}), 400

    active_users[user_id] = {"lat": lat, "lon": lon}
    return jsonify({"status": "Standort aktualisiert", "active_users_count": len(active_users)}), 200

@app.route('/send-message', methods=['POST'])
def send_message():
    """Nutzer schickt eine Nachricht"""
    data = request.get_json()
    user_id = data.get('user_id')
    text = data.get('text')
    lat = data.get('lat')
    lon = data.get('lon')

    if not text or lat is None or lon is None:
        return jsonify({"error": "Nachricht oder Standort fehlt"}), 400

    msg_obj = {
        "user_id": user_id,
        "text": text,
        "lat": lat,
        "lon": lon
    }
    messages_store.append(msg_obj)
    return jsonify({"status": "Gesendet"}), 200

@app.route('/get-nearby-messages', methods=['POST'])
def get_nearby_messages():
    """Holt alle Nachrichten, die sich im Umkreis von 500m befinden"""
    data = request.get_json()
    my_lat = data.get('lat')
    my_lon = data.get('lon')
    max_radius = 500 # 500 Meter Radius

    if my_lat is None or my_lon is None:
        return jsonify({"error": "Standort erforderlich"}), 400

    nearby_messages = []
    for msg in messages_store:
        dist = calculate_distance_meters(my_lat, my_lon, msg['lat'], msg['lon'])
        if dist <= max_radius:
            nearby_messages.append({
                "user_id": msg['user_id'],
                "text": msg['text'],
                "distance_m": round(dist)
            })

    return jsonify({"messages": nearby_messages}), 200

@app.route('/', methods=['GET'])
def home():
    return "Talk-to-Me Radius-Server läuft!", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)