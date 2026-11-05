import asyncio
import math
import random
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="LAN Kart")

# Fixed: Removed one `.parent` so it resolves to the folder containing main.py
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

clients: dict[WebSocket, str] = {}
finished_players: set[str] = set()
last_shot_at: dict[str, float] = {}
projectile_owners: dict[str, str] = {}

def generate_track_params():
    """Generate harmonics for a smooth, longer closed loop."""
    return {
        "h1_a": random.uniform(5, 12),
        "h1_p": random.uniform(0, 6.28),
        "h2_a": random.uniform(2, 6),
        "h2_p": random.uniform(0, 6.28),
        "h3_a": random.uniform(1, 4),
        "h3_p": random.uniform(0, 6.28),
        "h4_a": random.uniform(1, 9),
        "h4_p": random.uniform(0, 6.28),
    }

current_track = generate_track_params()

async def broadcast(message: dict, exclude: WebSocket | None = None):
    """Send a message to connected clients and discard broken connections."""
    stale = []
    for client in list(clients):
        if client is exclude:
            continue
        try:
            await client.send_json(message)
        except Exception:
            stale.append(client)

    for client in stale:
        clients.pop(client, None)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    global current_track

    await ws.accept()
    pid = uuid.uuid4().hex[:8]
    clients[ws] = pid
    last_shot_at[pid] = 0.0

    await ws.send_json({
        "type": "welcome",
        "id": pid,
        "track": current_track,
    })

    try:
        while True:
            data = await ws.receive_json()
            message_type = data.get("type")

            if message_type == "finish":
                if pid in finished_players:
                    continue

                finished_players.add(pid)
                await broadcast({"type": "winner", "id": pid})

                # Keep the existing short winner screen, then start a new race.
                await asyncio.sleep(4)

                current_track = generate_track_params()
                finished_players.clear()
                projectile_owners.clear()
                await broadcast({"type": "reset", "track": current_track})
                continue

            if message_type == "shoot":
                now = time.monotonic()
                if now - last_shot_at.get(pid, 0.0) < 0.7:
                    continue

                try:
                    x = float(data["x"])
                    z = float(data["z"])
                    ang = float(data["ang"])
                except (KeyError, TypeError, ValueError):
                    continue

                if not all(math.isfinite(v) for v in (x, z, ang)):
                    continue
                if abs(x) > 250 or abs(z) > 250:
                    continue

                last_shot_at[pid] = now
                projectile_id = uuid.uuid4().hex
                projectile_owners[projectile_id] = pid

                await broadcast({
                    "type": "shoot",
                    "projectile_id": projectile_id,
                    "owner": pid,
                    "x": x,
                    "z": z,
                    "ang": ang,
                })
                continue

            if message_type == "projectile_hit":
                projectile_id = str(data.get("projectile_id", ""))
                target = str(data.get("target", ""))

                # Only the player who fired a shell may report its hit.
                if projectile_owners.get(projectile_id) != pid:
                    continue
                if target not in clients.values() or target == pid:
                    continue

                try:
                    dx = float(data["dx"])
                    dz = float(data["dz"])
                except (KeyError, TypeError, ValueError):
                    continue

                if not all(math.isfinite(v) for v in (dx, dz)):
                    continue

                projectile_owners.pop(projectile_id, None)
                await broadcast({
                    "type": "projectile_hit",
                    "projectile_id": projectile_id,
                    "owner": pid,
                    "target": target,
                    "dx": max(-1.0, min(1.0, dx)),
                    "dz": max(-1.0, min(1.0, dz)),
                })
                continue

            if message_type == "state":
                try:
                    x = float(data["x"])
                    z = float(data["z"])
                    ang = float(data["ang"])
                    speed = float(data.get("speed", 0))
                except (KeyError, TypeError, ValueError):
                    continue

                if not all(math.isfinite(v) for v in (x, z, ang, speed)):
                    continue

                await broadcast({
                    "type": "state",
                    "id": pid,
                    "x": x,
                    "z": z,
                    "ang": ang,
                    "speed": speed,
                }, exclude=ws)

    except WebSocketDisconnect:
        pass
    finally:
        clients.pop(ws, None)
        last_shot_at.pop(pid, None)
        finished_players.discard(pid)

        # Remove projectiles owned by the disconnected player.
        for projectile_id, owner in list(projectile_owners.items()):
            if owner == pid:
                projectile_owners.pop(projectile_id, None)

        await broadcast({"type": "leave", "id": pid})

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Execute this file directly via `python main.py` to start the webserver
    uvicorn.run(app, host="127.0.0.1", port=8000)
