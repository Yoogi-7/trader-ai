# apps/api/main.py
from __future__ import annotations
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import router as api_router
from apps.api.websocket import router as ws_router
from apps.api.routers_webhooks import router as hooks_router
from apps.api.security import RateLimiter

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(title="Trader AI API", version="1.0.0")

# --- CORS: domyślnie zacieśniony (konfiguruj przez CORS_ORIGINS)
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET","POST","PUT","DELETE","OPTIONS"],
    allow_headers=["*"],
)

# --- Security / Rate limiting middleware
RATE_LIMIT = int(os.getenv("RATE_LIMIT_CAPACITY", "120"))
RATE_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app.add_middleware(
    RateLimiter,
    capacity=RATE_LIMIT,
    window_sec=RATE_WINDOW,
    redis_url=REDIS_URL,
    allowlist_prefixes=("/health", "/ws", "/docs", "/openapi.json"),
)

# REST
app.include_router(api_router)
app.include_router(hooks_router)

# WebSocket
app.include_router(ws_router)

@app.get("/health")
def health():
    return {"ok": True}
