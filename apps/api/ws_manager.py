# apps/api/ws_manager.py
# WebSocket manager + subskrypcja Redis (async) i broadcast do klientów.
from __future__ import annotations
import asyncio
import json
from typing import Set
from fastapi import WebSocket
import redis.asyncio as aioredis
from apps.api.config import settings

class WSManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._subscriber_task: asyncio.Task | None = None
        self._redis: aioredis.Redis | None = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            if ws in self.active:
                self.active.remove(ws)

    async def broadcast_json(self, payload: dict):
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def start_subscriber(self):
        # Uruchamiane na starcie aplikacji FastAPI
        self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe("signals", "progress")

        async def reader():
            async for msg in pubsub.listen():
                if msg is None:
                    await asyncio.sleep(0.05)
                    continue
                # msg = {'type': 'message', 'pattern': None, 'channel': 'signals', 'data': '...'}
                if msg.get("type") == "message":
                    chan = msg.get("channel")
                    data = msg.get("data")
                    try:
                        payload = json.loads(data)
                    except Exception:
                        payload = {"type": "raw", "channel": chan, "data": data}
                    await self.broadcast_json({"channel": chan, "payload": payload})

        self._subscriber_task = asyncio.create_task(reader())

    async def stop_subscriber(self):
        if self._subscriber_task:
            self._subscriber_task.cancel()
            with contextlib.suppress(Exception):
                await self._subscriber_task
        if self._redis:
            await self._redis.close()

manager = WSManager()
