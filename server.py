import math
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

app = FastAPI(title="Talk to Me - Walkie Talkie Backend")

# Speicher für aktive Verbindungen
# Format: { websocket: {"lat": float, "lng": float} }
active_connections: Dict[WebSocket, dict] = {}


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Berechnet die Distanz zwischen zwei GPS-Koordinaten in Metern (Haversine-Formel).
    """
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
    """
    Berechnet für jeden verbundenen Nutzer, wie viele andere Nutzer im 500m-Umkreis sind,
    und sendet diesen Wert als Nachricht an den Client.
    """
    for ws_client, data_client in active_connections.items():
        if data_client["lat"] is None or data_client["lng"] is None:
            continue

        nearby_count = 0
        for ws_other, data_other in active_connections.items():
            if ws_client == ws_other:
                continue

            if data_other["lat"] is not None and data_other["lng"] is not None:
                dist = calculate_distance(
                    data_client["lat"],
                    data_client["lng"],
                    data_other["lat"],
                    data_other["lng"],
                )
                if dist <= 500:  # 500 Meter Radius
                    nearby_count += 1

        # Sende die Anzahl der Leute im Umkreis an das jeweilige Handy
        try:
            await ws_client.send_json(
                {"type": "nearby_count", "count": nearby_count}
            )
        except Exception:
            pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Neue Verbindung akzeptieren
    await websocket.accept()
    active_connections[websocket] = {"lat": None, "lng": None}
    print(f"[+] Neuer Client verbunden: {websocket.client}")

    try:
        while True:
            # Nachrichten empfangen (Kann Text/JSON oder rohe Audio-Daten sein)
            message = await websocket.receive()

            # 1. Fall: GPS-Koordinaten erhalten (JSON)
            if "text" in message:
                import json

                data = json.loads(message["text"])

                if data.get("type") == "location":
                    active_connections[websocket]["lat"] = data.get("lat")
                    active_connections[websocket]["lng"] = data.get("lng")
                    # Alle Clients über geänderte Umkreis-Zahlen informieren
                    await update_nearby_users_count()

            # 2. Fall: Mikrofon-Audiodaten erhalten (Binärdaten/Bytes)
            elif "bytes" in message:
                audio_data = message["bytes"]
                client_location = active_connections[websocket]

                # Sende das Audio nur an Handys im Umkreis von 500 Metern!
                for ws_other, data_other in active_connections.items():
                    if ws_other == websocket:
                        continue  # Nicht an sich selbst senden

                    # Falls GPS vorhanden ist, prüfe Distanz
                    if (
                        client_location["lat"] is not None
                        and data_other["lat"] is not None
                    ):
                        dist = calculate_distance(
                            client_location["lat"],
                            client_location["lng"],
                            data_other["lat"],
                            data_other["lng"],
                        )
                        if dist <= 500:
                            await ws_other.send_bytes(audio_data)
                    else:
                        # Falls noch kein GPS da ist, sicherheitshalber senden
                        await ws_other.send_bytes(audio_data)

    except WebSocketDisconnect:
        print(f"[-] Client getrennt: {websocket.client}")
        del active_connections[websocket]
        await update_nearby_users_count()
    except Exception as e:
        print(f"[!] Fehler: {e}")
        if websocket in active_connections:
            del active_connections[websocket]


if __name__ == "__main__":
    # Startet den Server auf Port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)