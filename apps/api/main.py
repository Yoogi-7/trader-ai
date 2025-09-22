
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.routers import router as api_router
from apps.api.websocket import router as ws_router
from apps.api.security import RateLimiter
from apps.api.config import get_settings

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
settings = get_settings()

app = FastAPI(title=settings.API_TITLE, version="1.0.0")

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(RateLimiter())

app.include_router(api_router)
app.include_router(ws_router)
