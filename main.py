import asyncio
import json
import math
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        # Speichert verbundene Clients mit ihren Daten: { websocket: {"lat": float, "lng": float} }
        self.active_connections: Dict[WebSocket, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = {"lat": None, "lng": None}

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    # Berechnet die Distanz zwischen zwei GPS-Punkten in Metern (Haversine-Formel)
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        if None in (lat1, lon1, lat2, lon2):
            return float('inf')
        R = 6371000 # Erdradius in Metern
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # Aktualisiert die Anzeige auf allen Handys, wie viele andere Handys in 500m sind
    async def update_radar_counts(self):
        clients = list(self.active_connections.keys())
        for client in clients:
            loc = self.active_connections[client]
            if loc["lat"] is None:
                continue
            
            nearby_count = 0
            for other, other_loc in self.active_connections.items():
                if client != other and other_loc["lat"] is not None:
                    dist = self.calculate_distance(loc["lat"], loc["lng"], other_loc["lat"], other_loc["lng"])
                    if dist <= 500: # 500 Meter Umkreis
                        nearby_count += 1
            
            try:
                await client.send_text(json.dumps({"type": "nearby_count", "count": nearby_count}))
            except Exception:
                pass

    # Sende Audio NUR an andere Handys im Umkreis (NIEMALS an das eigene Absender-Handy)
    async def broadcast_audio(self, sender_websocket: WebSocket, audio_data: bytes):
        sender_loc = self.active_connections.get(sender_websocket)
        if not sender_loc or sender_loc["lat"] is None:
            return

        for client, loc in list(self.active_connections.items()):
            # WICHTIG: Überspringe das eigene Handy!
            if client == sender_websocket:
                continue

            if loc["lat"] is not None:
                dist = self.calculate_distance(sender_loc["lat"], sender_loc["lng"], loc["lat"], loc["lng"])
                if dist <= 500: # Nur im 500m Umkreis senden
                    try:
                        await client.send_bytes(audio_data)
                    except Exception:
                        pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Empfange Daten (entweder Text für GPS oder Bytes für Audio)
            message = await websocket.receive()
            
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "location":
                        manager.active_connections[websocket]["lat"] = data.get("lat")
                        manager.active_connections[websocket]["lng"] = data.get("lng")
                        await manager.update_radar_counts()
                except Exception as e:
                    print("JSON Fehler:", e)

            elif "bytes" in message:
                await manager.broadcast_audio(websocket, message["bytes"])

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.update_radar_counts()