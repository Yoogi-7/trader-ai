# apps/api/routers.py
from __future__ import annotations

import json
import time
from typing import List

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
from apps.ml.validators import (
    get_kill_switch,
    in_cooldown,
    set_cooldown,
    basic_market_checks,
    risk_profile_limits,
    correlation_cap,
    set_kill_switch,
)
from apps.ml.train.lightgbm_pipeline import run as run_lgbm

# Router główny API
router = APIRouter()


# ==== helpers ====
def get_db():
    """Zależność FastAPI – sesja DB per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _redis():
    """Połączenie do Redis (Pub/Sub do sygnałów / progresów)."""
    return redis.from_url("redis://redis:6379/0")


def _size_position(capital: float, risk: float, entry: float, sl: float, lev: int) -> float:
    """
    Sizing pozycji PAPER:
    qty ~ (capital * risk) / |entry - sl|, skorygowany o lev i wycenę kontraktu (linear USDT: dzielimy przez entry).
    """
    risk_cash = capital * risk
    dist = max(1e-6, abs(entry - sl))
    qty = (risk_cash / dist) * lev / entry
    return max(0.0, qty)


# ==== Backfill ====
@router.post("/backfill/start")
def backfill_start(req: BackfillStart, db: Session = Depends(get_db)):
    """
    Wrzuca zadanie backfill do kolejki (status=queued). Job ML odpala batchy i publikuje progres na kanale 'progress'.
    """
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


# ==== Training ====
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


@router.post("/train/run_lgbm")
def train_run_lgbm(req: TrainRun, db: Session = Depends(get_db)):
    """
    Uruchamia LightGBM + Optuna (OOS objective, Purged/Embargo).
    Metryki OOS lądują w TrainingRun.metrics_json.
    """
    symbol = (req.params or {}).get("symbol", "BTCUSDT")
    tf = (req.params or {}).get("tf", "15m")
    n_trials = int((req.params or {}).get("n_trials", 10))
    res = run_lgbm(symbol=symbol, tf=tf, n_trials=n_trials)
    return {"status": "done" if "error" not in res else "error", "metrics": res}


# ==== Backtests ====
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


# ==== Signals / Risk / Paper positions ====
@router.post("/signals/generate", response_model=List[SignalOut])
def signals_generate(req: SignalRequest, db: Session = Depends(get_db)):
    """
    Generuje sygnały na żądanie dla podanych par, z walidacjami:
      - kill-switch & cooldown,
      - limity profilu (lev/parallel),
      - walidacje rynkowe (spread/depth/funding),
      - korelacyjny cap (BTC/ETH vs capital),
      - twardy filtr >= 2% net (fee+slippage).
    Jeśli sygnał zostanie opublikowany -> tworzy paper position + nadaje event przez Redis ("signals").
    """
    if get_kill_switch() or in_cooldown():
        return []

    # Preferencje użytkownika (jeśli brak — z requestu)
    u = db.query(User).first()
    profile = (u.risk_profile if u else req.risk_profile or "LOW").upper()
    capital = float(u.capital if u else (req.capital or 100.0))

    # Liczba równoległych „świeżych” publikacji (15 min okno)
    fifteen_min_ago = int(time.time() * 1000) - 15 * 60 * 1000
    parallel_now = (
        db.query(Signal)
        .filter(Signal.ts >= fifteen_min_ago, Signal.status == "published")
        .count()
    )

    out: List[SignalOut] = []
    now_ms = int(time.time() * 1000)
    r = _redis()

    pairs = req.pairs or ["BTCUSDT", "ETHUSDT"]
    for sym in pairs:
        # Limity profilu
        ok, reason = risk_profile_limits(profile, requested_lev=5, current_parallel=parallel_now)
        if not ok:
            s = Signal(
                symbol=sym,
                tf_base="15m",
                ts=now_ms,
                dir="long",
                entry=100.0,
                sl=98.0,
                tp=[102.0, 103.0, 104.0],
                lev=5,
                risk=0.01,
                margin_mode="isolated",
                expected_net_pct=0.0,
                confidence=0.0,
                model_ver="v1",
                reason_discard=reason,
                status="discarded",
            )
            db.add(s)
            db.flush()
            continue

        # Walidacje rynku (spread/depth/funding)
        ok, reason = basic_market_checks(db, sym)
        if not ok:
            s = Signal(
                symbol=sym,
                tf_base="15m",
                ts=now_ms,
                dir="long",
                entry=100.0,
                sl=98.0,
                tp=[102.0, 103.0, 104.0],
                lev=5,
                risk=0.01,
                margin_mode="isolated",
                expected_net_pct=0.0,
                confidence=0.0,
                model_ver="v1",
                reason_discard=reason,
                status="discarded",
            )
            db.add(s)
            db.flush()
            continue

        # Korelacyjny cap BTC/ETH
        ok, reason = correlation_cap(db, user_capital=capital)
        if not ok:
            s = Signal(
                symbol=sym,
                tf_base="15m",
                ts=now_ms,
                dir="long",
                entry=100.0,
                sl=98.0,
                tp=[102.0, 103.0, 104.0],
                lev=5,
                risk=0.01,
                margin_mode="isolated",
                expected_net_pct=0.0,
                confidence=0.0,
                model_ver="v1",
                reason_discard=reason,
                status="discarded",
            )
            db.add(s)
            db.flush()
            continue

        # Filtr ≥ 2% net (upraszczamy: TP1)
        entry = 100.0
        sl = 98.0
        tp = [102.0, 103.0, 104.0]
        gross_gain_pct = (tp[0] - entry) / entry
        taker_fee = 2 * 0.001  # wejście+wyjście
        slippage = 0.0005
        net = gross_gain_pct - taker_fee - slippage
        status = "published" if net >= 0.02 else "discarded"
        reason = None if status == "published" else "<2% net"

        s = Signal(
            symbol=sym,
            tf_base="15m",
            ts=now_ms,
            dir="long",
            entry=entry,
            sl=sl,
            tp=tp,
            lev=5,
            risk=0.01,
            margin_mode="isolated",
            expected_net_pct=round(net * 100, 2),
            confidence=0.62,
            model_ver="v1",
            reason_discard=reason,
            status=status,
        )
        db.add(s)
        db.flush()

        if status == "published":
            # Utwórz PAPER position
            qty = _size_position(capital=capital, risk=s.risk, entry=s.entry, sl=s.sl, lev=s.lev)
            exposure_usd = qty * s.entry
            pos = Position(
                symbol=s.symbol,
                side=s.dir,
                entry_px=s.entry,
                qty=qty,
                lev=s.lev,
                margin_mode=s.margin_mode,
                exposure_usd=exposure_usd,
                opened_ts=now_ms,
                status="open",
                pnl=0.0,
            )
            db.add(pos)
            db.flush()

            # Wyślij przez Redis live event (kanał: signals)
            out_payload = dict(
                id=s.id,
                symbol=s.symbol,
                dir=s.dir,
                entry=s.entry,
                sl=s.sl,
                tp=s.tp,
                lev=s.lev,
                risk=s.risk,
                margin_mode=s.margin_mode,
                expected_net_pct=s.expected_net_pct,
                confidence=s.confidence,
                status=s.status,
                reason_discard=s.reason_discard,
                ts=now_ms,
                source="api",
            )
            r.publish("signals", json.dumps(out_payload))
            out.append(SignalOut(**out_payload))

    db.commit()
    return out


@router.get("/signals/history")
def signals_history(db: Session = Depends(get_db)):
    rows = db.query(Signal).order_by(Signal.id.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "symbol": r.symbol,
            "dir": r.dir,
            "entry": r.entry,
            "tp": r.tp,
            "sl": r.sl,
            "expected_net_pct": r.expected_net_pct,
            "confidence": r.confidence,
            "status": r.status,
            "ts": r.ts,
        }
        for r in rows
    ]


# ==== Settings (profil/kapitał) ====
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


# ==== Positions (paper) ====
@router.get("/positions/open")
def positions_open(db: Session = Depends(get_db)):
    rows = db.query(Position).filter(Position.status == "open").all()
    total = sum(abs(r.exposure_usd) for r in rows)
    return {
        "total_exposure_usd": total,
        "positions": [
            dict(
                id=r.id,
                symbol=r.symbol,
                side=r.side,
                entry_px=r.entry_px,
                qty=r.qty,
                lev=r.lev,
                exposure_usd=r.exposure_usd,
                opened_ts=r.opened_ts,
                status=r.status,
            )
            for r in rows
        ],
    }


# ==== Admin (kill-switch / cooldown) ====
@router.post("/admin/kill_switch")
def admin_kill_switch(on: bool):
    set_kill_switch(on)
    return {"kill_switch": on}


@router.post("/admin/cooldown")
def admin_cooldown(minutes: int = 30):
    if minutes < 1:
        raise HTTPException(status_code=400, detail="minutes must be >= 1")
    set_cooldown(minutes)
    return {"cooldown_minutes": minutes}
