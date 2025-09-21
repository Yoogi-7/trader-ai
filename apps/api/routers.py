from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from apps.api.db import SessionLocal
from apps.api.schemas import BackfillStart, TrainRun, BacktestRun, SignalRequest, SignalOut
from apps.api.models import Signal, BackfillProgress, TrainingRun, Backtest
from typing import List
import time

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/backfill/start")
def backfill_start(req: BackfillStart, db: Session = Depends(get_db)):
    # in prod: enqueue job to Kafka/Redis; here: create progress rows
    pairs = req.pairs or ["BTCUSDT","ETHUSDT"]
    for p in pairs:
        row = db.query(BackfillProgress).filter_by(symbol=p, tf=req.tf).one_or_none()
        if not row:
            row = BackfillProgress(symbol=p, tf=req.tf, status="queued", chunk_start_ts=req.since_ms or 0)
            db.add(row)
        else:
            row.status="queued"; row.retry_count=0
    db.commit()
    return {"status":"queued","pairs":pairs,"tf":req.tf}

@router.get("/backfill/status")
def backfill_status(db: Session = Depends(get_db)):
    rows = db.query(BackfillProgress).all()
    return [{"symbol":r.symbol,"tf":r.tf,"last_ts_completed":r.last_ts_completed,"status":r.status} for r in rows]

@router.post("/train/run")
def train_run(req: TrainRun, db: Session = Depends(get_db)):
    tr = TrainingRun(status="running", params_json=req.params, metrics_json={})
    db.add(tr); db.commit()
    return {"id": tr.id, "status": tr.status}

@router.get("/train/status")
def train_status(db: Session = Depends(get_db)):
    runs = db.query(TrainingRun).order_by(TrainingRun.id.desc()).limit(10).all()
    return [{"id":r.id,"status":r.status,"metrics":r.metrics_json} for r in runs]

@router.post("/backtest/run")
def backtest_run(req: BacktestRun, db: Session = Depends(get_db)):
    bt = Backtest(params_json=req.params, summary_json={})
    db.add(bt); db.commit()
    return {"id": bt.id, "status": "queued"}

@router.get("/backtest/results")
def backtest_results(db: Session = Depends(get_db)):
    res = db.query(Backtest).order_by(Backtest.id.desc()).limit(5).all()
    return [{"id":b.id,"summary":b.summary_json} for b in res]

@router.post("/signals/generate", response_model=List[SignalOut])
def signals_generate(req: SignalRequest, db: Session = Depends(get_db)):
    # minimal demo: random signals filtered by >=2% net rule
    out = []
    now = int(time.time()*1000)
    for sym in req.pairs:
        entry = 100.0
        sl = 98.0
        tp = [102.0, 103.0, 104.0]
        gross_gain_pct = (tp[0]-entry)/entry
        taker_fee = 2 * 0.001  # entry+exit (approx)
        slippage = 0.0005
        net = gross_gain_pct - taker_fee - slippage
        status = "published" if net >= 0.02 else "discarded"
        reason = None if status=="published" else "<2% net"
        s = Signal(symbol=sym, tf_base="15m", ts=now, dir="long", entry=entry, sl=sl,
                   tp=tp, lev=5, risk=0.01, margin_mode="isolated",
                   expected_net_pct=round(net*100,2), confidence=0.62,
                   model_ver="v1", reason_discard=reason, status=status)
        db.add(s); db.flush()
        if status=="published":
            out.append(SignalOut(id=s.id, symbol=s.symbol, dir=s.dir, entry=s.entry, sl=s.sl,
                                 tp=s.tp, lev=s.lev, risk=s.risk, margin_mode=s.margin_mode,
                                 expected_net_pct=s.expected_net_pct, confidence=s.confidence,
                                 status=s.status, reason_discard=s.reason_discard))
    db.commit()
    return out

@router.get("/signals/history")
def signals_history(db: Session = Depends(get_db)):
    rows = db.query(Signal).order_by(Signal.id.desc()).limit(50).all()
    return [{
        "id":r.id,"symbol":r.symbol,"dir":r.dir,"entry":r.entry,"tp":r.tp,"sl":r.sl,
        "expected_net_pct":r.expected_net_pct,"confidence":r.confidence,"status":r.status
    } for r in rows]