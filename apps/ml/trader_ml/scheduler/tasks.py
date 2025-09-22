from .celery_app import app
from ..data.backfill import backfill_ohlcv
import os

@app.task
def run_backfill(symbol: str):
    backfill_ohlcv(symbol, years=int(os.getenv("BACKFILL_YEARS","4")), tf=os.getenv("OHLCV_BASE_TF","1m"))
    return {"symbol": symbol, "status": "ok"}
