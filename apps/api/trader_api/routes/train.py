from fastapi import APIRouter
from ..schemas import TrainRunRequest
from ..redis_cache import r
import uuid

router = APIRouter(prefix="/train", tags=["train"])

@router.post("/run")
def run_train(req: TrainRunRequest):
    job_id = str(uuid.uuid4())
    r.hset(f"train:{job_id}", mapping={"status":"running","oos_hit_rate":"-", "message": "started"})
    return {"job_id": job_id, "status": "running"}

@router.get("/status")
def train_status(job_id: str):
    return r.hgetall(f"train:{job_id}") or {"status":"unknown"}
