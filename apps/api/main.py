from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apps.api.config import settings
from apps.api.db.models import UserToken
from apps.api.db.session import AsyncSessionLocal
from apps.api.routers import (
    signals,
    backtest,
    backfill,
    train,
    auto_train,
    settings as settings_router,
    system,
    users,
)
from apps.api.security import hash_token
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from starlette import status
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TraderAI API",
    description="AI-powered crypto futures trading signal system",
    version="1.0.0"
)

app.state.session_maker = AsyncSessionLocal

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(signals.router, prefix=f"{settings.API_V1_PREFIX}/signals", tags=["Signals"])
app.include_router(backtest.router, prefix=f"{settings.API_V1_PREFIX}/backtest", tags=["Backtest"])
app.include_router(backfill.router, prefix=f"{settings.API_V1_PREFIX}/backfill", tags=["Backfill"])
app.include_router(train.router, prefix=f"{settings.API_V1_PREFIX}/train", tags=["Training"])
app.include_router(auto_train.router, prefix=f"{settings.API_V1_PREFIX}", tags=["Auto-Training"])
app.include_router(settings_router.router, prefix=f"{settings.API_V1_PREFIX}/settings", tags=["Settings"])
app.include_router(system.router, prefix=f"{settings.API_V1_PREFIX}/system", tags=["System"])
app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["Users"])


UNPROTECTED_PATHS = {"/", "/health"}
UNPROTECTED_PREFIXES = ("/docs", "/openapi", "/redoc", "/static", "/ws")


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    path = request.url.path

    if request.method == "OPTIONS":
        return await call_next(request)

    if path in UNPROTECTED_PATHS or any(path.startswith(prefix) for prefix in UNPROTECTED_PREFIXES):
        return await call_next(request)

    session_maker = getattr(request.app.state, "session_maker", AsyncSessionLocal)

    async with session_maker() as session:
        try:
            existing_token_result = await session.execute(
                select(UserToken.id).where(UserToken.revoked.is_(False)).limit(1)
            )
            has_tokens = existing_token_result.scalar_one_or_none() is not None
        except ProgrammingError:
            await session.rollback()
            logger.info("User tokens table missing; skipping API key enforcement")
            has_tokens = False
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("Error checking user tokens: %s", exc)
            has_tokens = False

        if not has_tokens:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")

        if not api_key:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                api_key = auth_header.split(" ", 1)[1]

        if not api_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing API key"},
            )

        token_hash = hash_token(api_key)

        try:
            result = await session.execute(
                select(UserToken).where(
                    UserToken.token_hash == token_hash,
                    UserToken.revoked.is_(False),
                )
            )
            token = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("Error validating API key: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Error validating API key"},
            )

        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid API key"},
            )

        token.last_used_at = datetime.utcnow()
        await session.commit()
        request.state.user_id = token.user_id

    response = await call_next(request)
    return response


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
