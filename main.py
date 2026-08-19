import math
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_relative_position(lat1, lon1, lat2, lon2):
    R = 6371000
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    
    y = d_lat * R
    x = d_lon * R * math.cos(math.radians((lat1 + lat2) / 2))
    return x, y

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[dict] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        conn_info = {
            "ws": websocket,
            "lat": 52.5200,
            "lng": 13.4050,
            "username": "Anonym"
        }
        self.active_connections.append(conn_info)
        await self.broadcast_radar()
        return conn_info

    def disconnect(self, conn_info: dict):
        if conn_info in self.active_connections:
            self.active_connections.remove(conn_info)

    def update_info(self, conn_info: dict, lat: float, lng: float, username: str):
        try:
            conn_info["lat"] = float(lat)
            conn_info["lng"] = float(lng)
            if username:
                conn_info["username"] = str(username)
        except (ValueError, TypeError):
            pass

    async def broadcast_radar(self):
        total_online = len(self.active_connections)

        for target in self.active_connections:
            nearby_users = []
            
            for other in self.active_connections:
                if other is target:
                    continue

                dist = haversine(target["lat"], target["lng"], other["lat"], other["lng"])
                if dist <= 500:
                    rel_x, rel_y = get_relative_position(target["lat"], target["lng"], other["lat"], other["lng"])
                    nearby_users.append({
                        "username": other["username"],
                        "distance": round(dist),
                        "x": round(rel_x, 1),
                        "y": round(rel_y, 1)
                    })

            radar_data = {
                "type": "radar_update",
                "total_online": total_online,
                "nearby_users": nearby_users
            }
            
            try:
                await target["ws"].send_json(radar_data)
            except Exception:
                pass

    async def broadcast_audio(self, sender_info: dict, data: bytes):
        for target in self.active_connections:
            if target is sender_info:
                continue

            dist = haversine(sender_info["lat"], sender_info["lng"], target["lat"], target["lng"])
            if dist <= 500:
                try:
                    await target["ws"].send_bytes(data)
                except Exception:
                    pass

manager = ConnectionManager()

async def radar_loop():
    while True:
        await asyncio.sleep(1)
        await manager.broadcast_radar()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(radar_loop())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    conn_info = await manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive()
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "location":
                        manager.update_info(
                            conn_info, 
                            data["lat"], 
                            data["lng"], 
                            data.get("username", "Anonym")
                        )
                        # Nach Update direkt ein Radar-Signal erzwingen
                        await manager.broadcast_radar()
                except Exception:
                    pass
            elif "bytes" in message:
                await manager.broadcast_audio(conn_info, message["bytes"])
    except WebSocketDisconnect:
        manager.disconnect(conn_info)
        await manager.broadcast_radar()
    except Exception:
        manager.disconnect(conn_info)
        await manager.broadcast_radar()