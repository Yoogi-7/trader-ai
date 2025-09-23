# apps/api/routes/internal.py
# PL: Prywatny webhook na zdarzenia z event-busa (consumer) -> broadcast WS + zapis do Redis cache.
# EN: Private webhook for events from event-bus -> WS broadcast + Redis cache.

from fastapi import APIRouter, Header, HTTPException
from apps.api.ws import ws_manager
from apps.common.cache import set_json
from pydantic import BaseModel
from typing import Any, Dict, Optional

# Prosty sekret nagłówka, by nie wystawiać publicznie (warto zmienić w .env i proxy)
INTERNAL_SECRET = "changeme"  # nadpisz ENV/front-proxy w realu

router = APIRouter(prefix="/internal", tags=["internal"])

class EventIn(BaseModel):
    type: str
    payload: Dict[str, Any]

@router.post("/events")
async def post_event(evt: EventIn, x_internal_secret: Optional[str] = Header(default=None)):
    if x_internal_secret and x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")
    # cache wybranych typów
    if evt.type in ("backfill_progress", "signal_published", "train_started", "train_finished", "backtest_started", "backtest_finished"):
        set_json(f"last:{evt.type}", evt.payload, ttl=120)
    # broadcast
    try:
        await ws_manager.broadcast({"type": evt.type, **evt.payload})
    except Exception:
        pass
    return {"ok": True}
