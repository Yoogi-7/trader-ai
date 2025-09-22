from fastapi import APIRouter
from ..schemas import BackfillStartRequest
from ..config import settings
from ..redis_cache import r
import uuid
import time

router = APIRouter(prefix="/backfill", tags=["backfill"])

@router.post("/start")
def start_backfill(req: BackfillStartRequest):
    job_id = str(uuid.uuid4())
    # zapis do Redis - symulacja kolejki/monitoringu (realnie wysyłamy do Kafka)
    r.hset(f"backfill:{job_id}", mapping={"status":"queued","progress":"0","eta":"-"})
    # w realu: publish do TOPIC_BACKFILL
    return {"job_id": job_id, "status": "queued"}

@router.get("/status")
def backfill_status(job_id: str):
    data = r.hgetall(f"backfill:{job_id}")
    return data or {"status":"unknown"}
