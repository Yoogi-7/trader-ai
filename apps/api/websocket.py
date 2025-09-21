# apps/api/websocket.py
from __future__ import annotations
import json
import asyncio
import logging
from typing import Dict, Any, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

log = logging.getLogger("ws")

router = APIRouter()

REDIS_URL = "redis://redis:6379/0"
CHANNEL_SIGNALS = "signals"
CHANNEL_PROGRESS = "progress"

async def _subscribe(pub: aioredis.client.PubSub, channels):
    await pub.subscribe(*channels)
    log.info("Subscribed to: %s", channels)

async def _publisher_to_ws(pub: aioredis.client.PubSub, ws: WebSocket, channel_filter: Optional[str]):
    try:
        while True:
            msg = await pub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg is None:
                await asyncio.sleep(0.05)
                continue
            ch = msg["channel"].decode() if isinstance(msg["channel"], (bytes, bytearray)) else msg["channel"]
            if channel_filter and ch != channel_filter:
                continue
            data = msg["data"]
            if isinstance(data, (bytes, bytearray)):
                data = data.decode()
            try:
                payload = json.loads(data)
            except Exception:
                payload = {"raw": data}
            await ws.send_json({"channel": ch, "data": payload})
    except Exception as e:
        log.warning("publisher_to_ws ended: %s", e)

@router.websocket("/ws/live")
async def ws_live(
    websocket: WebSocket,
    channels: str = Query(default=f"{CHANNEL_SIGNALS},{CHANNEL_PROGRESS}", description="Comma-separated channels: signals,progress"),
    ping_interval: float = Query(default=20.0)
):
    """
    Live WS:
      - channels: np. "signals,progress" (domyślnie oba).
      - serwer proxy'uje publikacje z Redis Pub/Sub do klienta.
      - prosty ping/pong: klient może wysłać {"type":"ping"}.
    """
    await websocket.accept()
    subs = [c.strip() for c in channels.split(",") if c.strip()]
    # sanity map
    valid = set([CHANNEL_SIGNALS, CHANNEL_PROGRESS])
    subs = [c for c in subs if c in valid]
    if not subs:
        subs = [CHANNEL_SIGNALS]

    redis = aioredis.from_url(REDIS_URL, decode_responses=False)
    pub = redis.pubsub()
    await _subscribe(pub, subs)

    send_task = asyncio.create_task(_publisher_to_ws(pub, websocket, None))

    async def _pinger():
        # keepalive pings (opcjonalnie)
        while True:
            try:
                await asyncio.sleep(ping_interval)
                await websocket.send_json({"type": "ping"})
            except Exception:
                break

    ping_task = asyncio.create_task(_pinger())

    try:
        while True:
            msg = await websocket.receive_text()
            try:
                js = json.loads(msg)
            except Exception:
                js = {"raw": msg}
            if isinstance(js, dict) and js.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        ping_task.cancel()
        try:
            await pub.unsubscribe(*subs)
        except Exception:
            pass
        await pub.close()
        await redis.close()
        await websocket.close()
