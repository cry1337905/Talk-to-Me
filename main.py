import asyncio
import math
import os
import aiosqlite
import websockets

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

async def init_db():
    async with aiosqlite.connect("positions.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                user_id TEXT PRIMARY KEY,
                latitude REAL,
                longitude REAL
            )
        """)
        await db.commit()

async def save_position(user_id, lat, lon):
    async with aiosqlite.connect("positions.db") as db:
        await db.execute("INSERT OR REPLACE INTO positions VALUES (?, ?, ?)", (user_id, lat, lon))
        await db.commit()

async def get_nearby_users(my_lat, my_lon):
    nearby = []
    async with aiosqlite.connect("positions.db") as db:
        async with db.execute("SELECT user_id, latitude, longitude FROM positions") as cursor:
            async for row in cursor:
                user_id, lat, lon = row
                dist = haversine(my_lat, my_lon, lat, lon)
                if dist <= 500:
                    nearby.append(user_id)
    return nearby

connected_clients = {}

async def handler(websocket):
    try:
        async for message in websocket:
            data = message.split(';')
            if len(data) >= 3:
                user_id = data[0]
                lat = float(data[1])
                lon = float(data[2])

                await save_position(user_id, lat, lon)
                connected_clients[user_id] = websocket

                nearby_users = await get_nearby_users(lat, lon)

                if len(data) > 3:
                    chat_message = data[3]
                    for other_user_id in nearby_users:
                        if other_user_id in connected_clients:
                            try:
                                await connected_clients[other_user_id].send(f"[Chat] {user_id}: {chat_message}")
                            except websockets.exceptions.ConnectionClosed:
                                connected_clients.pop(other_user_id, None)
                else:
                    for other_user_id in nearby_users:
                        if other_user_id in connected_clients:
                            try:
                                await connected_clients[other_user_id].send(f"Fahrzeug {user_id} ist in deiner Nähe.")
                            except websockets.exceptions.ConnectionClosed:
                                connected_clients.pop(other_user_id, None)

                await websocket.send(f"Aktive Fahrzeuge in deiner Nähe: {', '.join(nearby_users)}")
    finally:
        for user_id, ws in connected_clients.items():
            if ws == websocket:
                connected_clients.pop(user_id, None)
                break

async def main():
    await init_db()
    # Liest den Port von Render aus (Standard ist sonst 8765)
    port = int(os.environ.get("PORT", 8765))
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())