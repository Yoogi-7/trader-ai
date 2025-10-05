from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from apps.api.config import settings
from apps.api.routers import auth, signals, backtest, backfill, train, settings as settings_router, system
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TraderAI API",
    description="AI-powered crypto futures trading signal system",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Auth"])
app.include_router(signals.router, prefix=f"{settings.API_V1_PREFIX}/signals", tags=["Signals"])
app.include_router(backtest.router, prefix=f"{settings.API_V1_PREFIX}/backtest", tags=["Backtest"])
app.include_router(backfill.router, prefix=f"{settings.API_V1_PREFIX}/backfill", tags=["Backfill"])
app.include_router(train.router, prefix=f"{settings.API_V1_PREFIX}/train", tags=["Training"])
app.include_router(settings_router.router, prefix=f"{settings.API_V1_PREFIX}/settings", tags=["Settings"])
app.include_router(system.router, prefix=f"{settings.API_V1_PREFIX}/system", tags=["System"])


# WebSocket connection manager for live signals
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/")
async def root():
    return {
        "service": "TraderAI API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
