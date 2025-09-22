
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json, asyncio, time

router = APIRouter()

@router.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws.accept()
    try:
        t = 0
        while True:
            t += 1
            await ws.send_text(json.dumps({"type":"heartbeat","t":t,"ts":time.time()}))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
