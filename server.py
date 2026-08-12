import json
import math
import os
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Talk to Me - Global Walkie Talkie Backend")

# CORS aktivieren, damit GitHub Pages und mobile WebViews zugreifen dürfen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Speicher für alle aktiven WebSocket-Verbindungen
# Struktur: { websocket_object: {"lat": float, "lng": float} }
active_connections: Dict[WebSocket, dict] = {}


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Berechnet die Entfernung zwischen zwei GPS-Koordinaten in Metern (Haversine-Formel)."""
    R = 6371000  # Erdradius in Metern
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c  # Distanz in Metern


async def update_nearby_users_count():
    """Berechnet für jeden Nutzer die Anzahl anderer aktiver Geräte im 500m-Umkreis

    und sendet diesen Wert live an das jeweilige Handy.
    """
    for ws_client, data_client in list(active_connections.items()):
        nearby_count = 0

        # Wenn der Nutzer noch kein GPS gesendet hat, bleibt die Zählung bei 0
        if data_client["lat"] is not None and data_client["lng"] is not None:
            for ws_other, data_other in active_connections.items():
                if ws_client == ws_other:
                    continue  # Nicht sich selbst mitzählen

                if (
                    data_other["lat"] is not None
                    and data_other["lng"] is not None
                ):
                    dist = calculate_distance(
                        data_client["lat"],
                        data_client["lng"],
                        data_other["lat"],
                        data_other["lng"],
                    )
                    if dist <= 500:  # 500 Meter Radius
                        nearby_count += 1

        # Aktualisierte Zahl an den Client senden
        try:
            await ws_client.send_text(
                json.dumps({"type": "nearby_count", "count": nearby_count})
            )
        except Exception:
            pass


@app.get("/")
def health_check():
    """Gesundheitscheck für Render.com"""
    return {
        "status": "online",
        "active_users": len(active_connections),
        "app": "Talk to Me Backend",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Neue Verbindung annehmen
    await websocket.accept()
    active_connections[websocket] = {"lat": None, "lng": None}
    print(f"[+] Neues Handy verbunden. Aktive Nutzer: {len(active_connections)}")

    try:
        while True:
            # Nachrichten empfangen (kann Text/JSON mit GPS oder rohes Audio sein)
            message = await websocket.receive()

            # 1. Fall: GPS-Standort empfangen
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "location":
                        active_connections[websocket]["lat"] = data.get("lat")
                        active_connections[websocket]["lng"] = data.get("lng")

                        # Nach jedem GPS-Update alle Umkreis-Zähler neu berechnen
                        await update_nearby_users_count()
                except json.JSONDecodeError:
                    pass

            # 2. Fall: Audio-Stream empfangen (Binärdaten / Bytes)
            elif "bytes" in message:
                audio_data = message["bytes"]
                sender_coords = active_connections[websocket]

                # Sprachdaten nur an Handys im 500m-Umkreis weiterschicken
                for ws_other, data_other in list(active_connections.items()):
                    if ws_other == websocket:
                        continue  # Sprachsignal nicht an den Sprecher selbst zurücksenden

                    # Wenn beide GPS haben: Distanz prüfen
                    if (
                        sender_coords["lat"] is not None
                        and data_other["lat"] is not None
                    ):
                        dist = calculate_distance(
                            sender_coords["lat"],
                            sender_coords["lng"],
                            data_other["lat"],
                            data_other["lng"],
                        )
                        if dist <= 500:
                            await ws_other.send_bytes(audio_data)
                    else:
                        # Fallback: Sprachdaten übertragen, falls GPS noch lädt
                        await ws_other.send_bytes(audio_data)

    except WebSocketDisconnect:
        print("[-] Handy getrennt")
    except Exception as e:
        print(f"[!] Fehler: {e}")
    finally:
        if websocket in active_connections:
            del active_connections[websocket]
        await update_nearby_users_count()


if __name__ == "__main__":
    # Dynamischen Port von Render auslesen oder Standard-Port 8000 nutzen
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)