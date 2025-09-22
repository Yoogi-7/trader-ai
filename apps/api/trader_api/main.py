from fastapi import FastAPI
from .config import settings
from .routes import signals, backfill, backtest, train
from .ws.live import router as ws_router

app = FastAPI(title=settings.API_TITLE)

app.include_router(signals.router)
app.include_router(backfill.router)
app.include_router(train.router)
app.include_router(backtest.router)
app.include_router(ws_router)
