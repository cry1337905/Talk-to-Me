from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import math
import asyncio
import time

app = FastAPI()

@app.get("/test")
def test_version():
    return {"status": "NEUER_CODE_IST_LIVE_V3_WITH_HEARTBEAT"}

class ConnectionManager:
    def __init__(self):
        # Nutzt das WebSocket-Objekt direkt als Key
        self.active_connections = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = {
            "id": str(id(websocket)),
            "lat": 0.0,
            "lng": 0.0,
            "username": "Anonym",
            "last_seen": time.time()  # Zeitstempel für Inaktivitäts-Prüfung
        }

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    def update_heartbeat(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections[websocket]["last_seen"] = time.time()

    async def check_inactive_connections(self):
        """ Entfernt Clients, die sich länger als 10 Sekunden nicht gemeldet haben """
        while True:
            await asyncio.sleep(5)  # Prüft alle 5 Sekunden
            now = time.time()
            to_remove = []

            for ws, info in list(self.active_connections.items()):
                # Wenn länger als 10 Sekunden kein Heartbeat/Location-Update kam
                if now - info["last_seen"] > 10:
                    to_remove.append(ws)

            if to_remove:
                for ws in to_remove:
                    self.disconnect(ws)
                    try:
                        await ws.close()
                    except Exception:
                        pass
                # Aktualisiere das Radar für alle verbleibenden Nutzer
                await self.broadcast_radar_data()

    async def broadcast_radar_data(self):
        total_online = len(self.active_connections)
        
        for ws, info in list(self.active_connections.items()):
            nearby_users = []
            
            for other_ws, other_info in list(self.active_connections.items()):
                if ws != other_ws:
                    # Entfernungsberechnung (Haversine)
                    dist = haversine(info['lat'], info['lng'], other_info['lat'], other_info['lng'])
                    
                    if dist <= 500:  # Umkreis von 500 Metern
                        rel_x = (other_info['lng'] - info['lng']) * 71500
                        rel_y = (other_info['lat'] - info['lat']) * 111300
                        
                        nearby_users.append({
                            "id": other_info["id"],
                            "username": other_info["username"],
                            "lat": other_info["lat"],
                            "lng": other_info["lng"],
                            "latitude": other_info["lat"],
                            "longitude": other_info["lng"],
                            "distance": round(dist),
                            "x": rel_x,
                            "y": rel_y
                        })
            
            payload = {
                "type": "radar_update",
                "total_online": total_online,
                "nearby_users": nearby_users
            }
            
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                pass

    async def broadcast_audio(self, sender_ws: WebSocket, audio_data: bytes):
        for ws in list(self.active_connections.keys()):
            if ws != sender_ws:
                try:
                    await ws.send_bytes(audio_data)
                except Exception:
                    pass

manager = ConnectionManager()

# Startet den Hintergrund-Loop zur Überprüfung inaktiver Nutzer beim Serverstart
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(manager.check_inactive_connections())

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi_1 = math.radians(lat1)
    phi_2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi_1) * math.cos(phi_2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive()
            
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    
                    # Heartbeat-Zeitstempel bei jeder Textnachricht auffrischen
                    manager.update_heartbeat(websocket)

                    action_type = data.get("type") or data.get("action")

                    # Manuelles Trennsignal vom Frontend bearbeiten
                    if action_type == "disconnect":
                        manager.disconnect(websocket)
                        await manager.broadcast_radar_data()
                        break

                    # Positions- / Heartbeat-Daten verarbeiten
                    if action_type == "location":
                        manager.active_connections[websocket]["lat"] = data.get("lat", 0.0)
                        manager.active_connections[websocket]["lng"] = data.get("lng", 0.0)
                        manager.active_connections[websocket]["username"] = data.get("username", "Anonym")
                        if "client_id" in data:
                            manager.active_connections[websocket]["id"] = data["client_id"]
                        
                        await manager.broadcast_radar_data()
                except Exception as e:
                    pass
                    
            elif "bytes" in message:
                manager.update_heartbeat(websocket)
                await manager.broadcast_audio(websocket, message["bytes"])
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast_radar_data()