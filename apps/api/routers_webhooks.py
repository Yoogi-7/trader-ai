# apps/api/routers_webhooks.py
from __future__ import annotations
import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.integrations.webhooks import send_discord, send_telegram, format_signal_message

router = APIRouter(prefix="/hooks", tags=["hooks"])

class HookTestPayload(BaseModel):
    symbol: str = "BTCUSDT"
    dir: str = "long"
    entry: float = 100.0
    sl: float = 98.0
    tp: list[float] = [102.0, 103.0, 104.0]
    lev: int = 5
    risk: float = 0.01
    expected_net_pct: float = 2.1
    confidence: float = 0.62

@router.get("/status")
def hooks_status():
    return {
        "discord_configured": bool(os.getenv("DISCORD_WEBHOOK_URL")),
        "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")),
    }

@router.post("/test/discord")
def test_discord(payload: HookTestPayload):
    ok = send_discord(format_signal_message(payload.dict()))
    if not ok:
        raise HTTPException(status_code=503, detail="Discord webhook failed (check env)")
    return {"ok": True}

@router.post("/test/telegram")
def test_telegram(payload: HookTestPayload):
    ok = send_telegram(format_signal_message(payload.dict()))
    if not ok:
        raise HTTPException(status_code=503, detail="Telegram send failed (check env)")
    return {"ok": True}
