# apps/api/main.py
from __future__ import annotations
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import router as api_router
from apps.api.websocket import router as ws_router
from apps.api.routers_webhooks import router as hooks_router

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(title="Trader AI API", version="1.0.0")

# CORS (zacieśnij w prod)
origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST
app.include_router(api_router)
app.include_router(hooks_router)

# WebSocket
app.include_router(ws_router)

@app.get("/health")
def health():
    return {"ok": True}
