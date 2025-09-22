
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from apps.api.routers import router
from apps.api.db.base import Base
from apps.api.db.session import engine
from apps.api.config import settings
import asyncio, json, time

app = FastAPI(title="Trader AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables (for dev). In prod, rely on Alembic migrations.
Base.metadata.create_all(bind=engine)

app.include_router(router)

# Simple WebSocket broadcaster (demo)
clients: set[WebSocket] = set()

@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            # heartbeats / demo messages
            await asyncio.sleep(5)
            msg = {"type": "heartbeat", "ts": int(time.time()*1000)}
            await ws.send_text(json.dumps(msg))
    except WebSocketDisconnect:
        clients.discard(ws)
