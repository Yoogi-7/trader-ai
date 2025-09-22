from fastapi import APIRouter, WebSocket
import json

router = APIRouter()

@router.websocket("/ws/live")
async def live(ws: WebSocket):
    await ws.accept()
    # simple heartbeat + fake messages; real feed: Kafka->API push
    await ws.send_text(json.dumps({"type":"hello","msg":"live feed ready"}))
    # client drives; close when done
