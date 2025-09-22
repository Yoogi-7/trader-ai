from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import get_settings

settings = get_settings()

app = FastAPI(title="Trader AI API", version="1.0.0")

# CORS
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/health")
def health():
    return {"status": "ok"}

# tutaj możesz mieć resztę routerów, np.:
# from apps.api.routes import router as api_router
# app.include_router(api_router)
