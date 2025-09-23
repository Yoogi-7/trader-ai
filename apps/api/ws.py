# apps/api/ws.py
# PL: Prosty manager WebSocket do broadcastu eventów. EN: Simple WS manager.

from typing import Set
from fastapi import WebSocket

class WSManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        to_drop = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                to_drop.append(ws)
        for ws in to_drop:
            self.disconnect(ws)

ws_manager = WSManager()
