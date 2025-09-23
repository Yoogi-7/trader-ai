# apps/api/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from apps.api.config import settings
from apps.api.routes import backfill, train, backtest, signals, settings as settings_routes
from apps.api.routes import internal  # NEW
from apps.api.ws import ws_manager
from apps.api.routes import signals as signals_routes


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backfill.router, prefix=settings.api_prefix)
app.include_router(train.router, prefix=settings.api_prefix)
app.include_router(backtest.router, prefix=settings.api_prefix)
app.include_router(signals.router, prefix=settings.api_prefix)
app.include_router(signals_routes.router, prefix="/api")
app.include_router(settings_routes.router, prefix=settings.api_prefix)
app.include_router(internal.router, prefix=settings.api_prefix)  # NEW

@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)

@app.get("/healthz")
def health():
    return {"ok": True, "name": settings.app_name, "version": settings.version}
