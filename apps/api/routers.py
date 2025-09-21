# apps/api/routers.py
from __future__ import annotations

import json
import time
from typing import List, Dict

import redis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.db import SessionLocal
from apps.api.schemas import (
    BackfillStart,
    TrainRun,
    BacktestRun,
    SignalRequest,
    SignalOut,
)
from apps.api.models import (
    Signal,
    BackfillProgress,
    TrainingRun,
    Backtest,
    User,
    Position,
)
from apps.api.security import require_role
from apps.ml.risk.engine import (
    apply_caps_and_sizing,
    quality_filter_2pct,
)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _redis():
    return redis.from_url("redis://redis:6379/0")

@router.post("/backfill/start")
def backfill_start(req: BackfillStart, db: Session = Depends(get_db)):
    pairs = req.pairs or ["BTCUSDT", "ETHUSDT"]
    for p in pairs:
        row = db.query(BackfillProgress).filter_by(symbol=p, tf=req.tf).one_or_none()
        if not row:
            row = BackfillProgress(
                symbol=p,
                tf=req.tf,
                status="queued",
                chunk_start_ts=req.since_ms or 0,
                chunk_end_ts=0,
                retry_count=0,
            )
            db.add(row)
        else:
            row.status = "queued"
            row.retry_count = 0
            if req.since_ms:
                row.chunk_start_ts = req.since_ms
    db.commit()
    return {"status": "queued", "pairs": pairs, "tf": req.tf, "since_ms": req.since_ms}

@router.get("/backfill/status")
def backfill_status(db: Session = Depends(get_db)):
    rows = db.query(BackfillProgress).all()
    return [
        {
            "symbol": r.symbol,
            "tf": r.tf,
            "last_ts_completed": r.last_ts_completed,
            "chunk_start_ts": r.chunk_start_ts,
            "chunk_end_ts": r.chunk_end_ts,
            "retry_count": r.retry_count,
            "status": r.status,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]

@router.post("/train/run")
def train_run(req: TrainRun, db: Session = Depends(get_db)):
    tr = TrainingRun(status="running", params_json=req.params or {}, metrics_json={})
    db.add(tr)
    db.commit()
    return {"id": tr.id, "status": tr.status}

@router.get("/train/status")
def train_status(db: Session = Depends(get_db)):
    runs = db.query(TrainingRun).order_by(TrainingRun.id.desc()).limit(10).all()
    return [
        {"id": r.id, "status": r.status, "metrics": r.metrics_json, "params": r.params_json}
        for r in runs
    ]

@router.post("/backtest/run")
def backtest_run(req: BacktestRun, db: Session = Depends(get_db)):
    bt = Backtest(params_json=req.params or {}, summary_json={})
    db.add(bt)
    db.commit()
    return {"id": bt.id, "status": "queued"}

@router.get("/backtest/results")
def backtest_results(db: Session = Depends(get_db)):
    res = db.query(Backtest).order_by(Backtest.id.desc()).limit(5).all()
    return [{"id": b.id, "summary": b.summary_json, "params": b.params_json} for b in res]

@router.post("/signals/generate", response_model=List[SignalOut])
def signals_generate(req: SignalRequest, db: Session = Depends(get_db)):
    # User & profile
    u = db.query(User).first()
    profile = (u.risk_profile if u else req.risk_profile or "LOW").upper()
    capital = float(u.capital if u else (req.capital or 100.0))

    # Zlicz równoległe pozycje w krótkim oknie (tu: wszystkie open)
    parallel_now = db.query(Position).filter(Position.status == "open").count()

    # Ekspozycje per symbol (open)
    rows = db.query(Position).filter(Position.status == "open").all()
    exposure_by_symbol: Dict[str, float] = {}
    for r in rows:
        exposure_by_symbol[r.symbol] = exposure_by_symbol.get(r.symbol, 0.0) + abs(r.exposure_usd)

    out: List[SignalOut] = []
    now_ms = int(time.time() * 1000)
    r = _redis()

    pairs = req.pairs or ["BTCUSDT", "ETHUSDT"]
    for sym in pairs:
        # Prosty przykład poziomów — w produkcji generuje to engine sygnałów (MTF+ATR/Fibo/S/R)
        entry = 100.0
        sl = 98.0
        tp = [102.2, 103.5, 105.0]  # TP1/TP2/TP3

        # Filtr jakości ≥2% netto (maker-first preferowany)
        ok_quality, net_pct = quality_filter_2pct(entry, tp[0], maker_first=True, holding_hours=8.0)
        if not ok_quality:
            s = Signal(
                symbol=sym, tf_base="15m", ts=now_ms, dir="long",
                entry=entry, sl=sl, tp=tp, lev=0, risk=0.0,
                margin_mode="isolated", expected_net_pct=round(net_pct, 2),
                confidence=0.0, model_ver="v1", reason_discard="<2% net", status="discarded",
            )
            db.add(s); db.flush()
            continue

        # Risk engine – limity profilu, caps, korelacja, sizing, lev, likwidacja
        sizing = apply_caps_and_sizing(
            symbol=sym, side="long", entry=entry, sl=sl,
            capital_usd=capital, profile_name=profile,
            existing_parallel_positions=parallel_now,
            current_exposure_by_symbol=exposure_by_symbol,
            requested_leverage=None,
        )
        if sizing.reason_block:
            s = Signal(
                symbol=sym, tf_base="15m", ts=now_ms, dir="long",
                entry=entry, sl=sl, tp=tp, lev=sizing.leverage, risk=0.0,
                margin_mode="isolated", expected_net_pct=round(net_pct, 2),
                confidence=0.0, model_ver="v1", reason_discard=sizing.reason_block, status="discarded",
            )
            db.add(s); db.flush()
            continue

        # Publikujemy sygnał
        s = Signal(
            symbol=sym, tf_base="15m", ts=now_ms, dir="long",
            entry=entry, sl=sl, tp=tp, lev=sizing.leverage, risk=0.0,
            margin_mode="isolated", expected_net_pct=round(net_pct, 2),
            confidence=0.62, model_ver="v1", reason_discard=None, status="published",
        )
        db.add(s); db.flush()

        # Otwórz pozycję (paper/shadow)
        pos = Position(
            symbol=s.symbol, side=s.dir, entry_px=s.entry, qty=sizing.qty, lev=sizing.leverage,
            margin_mode=s.margin_mode, exposure_usd=sizing.exposure_usd, opened_ts=now_ms,
            status="open", pnl=0.0,
        )
        db.add(pos); db.flush()

        out_payload = dict(
            id=s.id, symbol=s.symbol, dir=s.dir, entry=s.entry, sl=s.sl, tp=s.tp,
            lev=s.lev, risk=s.risk, margin_mode=s.margin_mode,
            expected_net_pct=s.expected_net_pct, confidence=s.confidence,
            status=s.status, reason_discard=s.reason_discard, ts=now_ms, source="api",
        )
        r.publish("signals", json.dumps(out_payload))
        out.append(SignalOut(**out_payload))

        # zaktualizuj kontekst ekspozycji i równoległość dla kolejnych par
        parallel_now += 1
        exposure_by_symbol[sym] = exposure_by_symbol.get(sym, 0.0) + abs(sizing.exposure_usd)

    db.commit()
    return out

@router.get("/signals/history")
def signals_history(db: Session = Depends(get_db)):
    rows = db.query(Signal).order_by(Signal.id.desc()).limit(100).all()
    return [
        {
            "id": r.id, "symbol": r.symbol, "dir": r.dir, "entry": r.entry,
            "tp": r.tp, "sl": r.sl, "expected_net_pct": r.expected_net_pct,
            "confidence": r.confidence, "status": r.status, "ts": r.ts,
        }
        for r in rows
    ]

@router.post("/settings/profile")
def set_profile(risk_profile: str, db: Session = Depends(get_db)):
    rp = (risk_profile or "LOW").upper()
    if rp not in ("LOW", "MED", "HIGH"):
        raise HTTPException(status_code=400, detail="risk_profile must be LOW|MED|HIGH")
    u = db.query(User).first()
    if not u:
        u = User(risk_profile=rp, capital=100.0, prefs={}, api_connected=False)
        db.add(u)
    else:
        u.risk_profile = rp
    db.commit()
    return {"ok": True, "risk_profile": u.risk_profile}

@router.post("/capital")
def set_capital(capital: float, db: Session = Depends(get_db)):
    if capital <= 0:
        raise HTTPException(status_code=400, detail="capital must be > 0")
    u = db.query(User).first()
    if not u:
        u = User(risk_profile="LOW", capital=capital, prefs={}, api_connected=False)
        db.add(u)
    else:
        u.capital = float(capital)
    db.commit()
    return {"ok": True, "capital": u.capital}

@router.get("/positions/open")
def positions_open(db: Session = Depends(get_db)):
    rows = db.query(Position).filter(Position.status == "open").all()
    total = sum(abs(r.exposure_usd) for r in rows)
    return {
        "total_exposure_usd": total,
        "positions": [
            dict(
                id=r.id, symbol=r.symbol, side=r.side, entry_px=r.entry_px, qty=r.qty,
                lev=r.lev, exposure_usd=r.exposure_usd, opened_ts=r.opened_ts, status=r.status,
            ) for r in rows
        ],
    }

# Admin – ochrona kluczem (require_role("admin")) – endpoints zostają jak były, zakładam że masz je już w main/security
@router.post("/admin/kill_switch", dependencies=[require_role("admin")])
def admin_kill_switch(on: bool):
    from apps.ml.validators import set_kill_switch
    set_kill_switch(on)
    return {"kill_switch": on}

@router.post("/admin/cooldown", dependencies=[require_role("admin")])
def admin_cooldown(minutes: int = 30):
    from apps.ml.validators import set_cooldown
    if minutes < 1:
        raise HTTPException(status_code=400, detail="minutes must be >= 1")
    set_cooldown(minutes)
    return {"cooldown_minutes": minutes}
