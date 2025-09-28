# apps/api/routes/signals.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from typing import Optional, Literal
from pydantic import BaseModel, Field
from apps.api.db.session import SessionLocal
from apps.api.db import models
from apps.api.services.signals_service import evaluate_signal
from apps.ml.arbitrage import ExchangePriceFetcher
from apps.api import schemas

router = APIRouter(prefix="/signals", tags=["signals"])

def db_dep():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class AutoReq(BaseModel):
    symbol: str
    tf_base: Literal["15m","1h","4h"] = "15m"
    ts: int = Field(..., description="epoch ms")
    direction: Literal["LONG","SHORT"]
    close: float
    atr: float
    fibo: Optional[dict] = None
    risk_profile: Literal["LOW","MED","HIGH"] = "LOW"
    capital: float = 100.0
    funding_rate_hourly: float = 0.0
    max_allocation_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0)

@router.post("/auto")
def generate_auto(req: AutoReq, db: Session = Depends(db_dep)):
    sig, reason = evaluate_signal(
        db=db, symbol=req.symbol, tf_base=req.tf_base, ts=req.ts, direction=req.direction,
        close=req.close, atr=req.atr, fibo=req.fibo, risk_profile=req.risk_profile,
        capital=req.capital, funding_rate_hourly=req.funding_rate_hourly,
        max_allocation_pct=req.max_allocation_pct,
    )
    if sig is None:
        raise HTTPException(status_code=400, detail={"reason": reason})
    return {
        "id": sig.id, "symbol": sig.symbol, "tf_base": sig.tf_base, "ts": sig.ts, "dir": sig.dir,
        "entry": sig.entry, "tp": sig.tp, "sl": sig.sl, "lev": sig.lev, "risk": sig.risk,
        "margin_mode": sig.margin_mode, "expected_net_pct": sig.expected_net_pct,
        "confidence": sig.confidence,
        "confidence_rating": int(round(float(sig.confidence) * 100.0)) if sig.confidence is not None else None,
        "market_regime": getattr(sig, "market_regime", None),
        "model_ver": sig.model_ver, "status": sig.status
    }


@router.post("/arbitrage/scan", response_model=schemas.ArbitrageScanResp)
def arbitrage_scan(payload: schemas.ArbitrageScanReq):
    if not payload.symbols:
        raise HTTPException(status_code=400, detail="symbols_required")
    if len(payload.exchanges) < 2:
        raise HTTPException(status_code=400, detail="at_least_two_exchanges")
    try:
        fetcher = ExchangePriceFetcher(payload.exchanges, market_type=payload.market_type)
        opportunities = fetcher.scan(payload.symbols, min_spread_pct=payload.min_spread_pct)
    except Exception as exc:  # pragma: no cover - network failures
        raise HTTPException(status_code=500, detail=f"arbitrage_scan_failed: {exc}") from exc
    return schemas.ArbitrageScanResp(opportunities=[
        schemas.ArbitrageOpportunity(
            symbol=o.symbol,
            buy_exchange=o.buy_exchange,
            sell_exchange=o.sell_exchange,
            buy_price=o.buy_price,
            sell_price=o.sell_price,
            spread_pct=o.spread_pct,
            timestamp_ms=o.timestamp_ms,
        )
        for o in opportunities
    ])

@router.get("/history")
def history(symbol: Optional[str] = None, limit: int = 100, offset: int = 0, db: Session = Depends(db_dep)):
    q = select(models.Signal)
    if symbol:
        q = q.where(models.Signal.symbol == symbol)
    q = q.order_by(desc(models.Signal.ts)).limit(limit).offset(offset)
    rows = db.execute(q).scalars().all()
    return {"total": len(rows), "items": [
        {
            "id": s.id, "symbol": s.symbol, "tf_base": s.tf_base, "ts": s.ts, "dir": s.dir,
            "entry": s.entry, "tp": s.tp, "sl": s.sl, "lev": s.lev, "risk": s.risk,
            "margin_mode": s.margin_mode, "expected_net_pct": s.expected_net_pct,
            "confidence": s.confidence,
            "confidence_rating": int(round(float(s.confidence) * 100.0)) if s.confidence is not None else None,
            "market_regime": getattr(s, "market_regime", None),
            "model_ver": s.model_ver, "status": s.status
        } for s in rows
    ]}
