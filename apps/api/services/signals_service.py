# apps/api/services/signals_service.py
from __future__ import annotations
import os
import time
import uuid
from typing import Optional, Literal, Dict, Any, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from apps.api.db import models
from apps.ml.signal_engine import build_proposal, SignalProposal
from apps.ml.risk import position_size, leverage_for, estimate_liquidation_price, check_caps, DEFAULT_CAPITAL
from apps.ml.costs import expected_net_pct
from apps.common.event_bus import publish  # NEW

MIN_NET_PROFIT = float(os.getenv("MIN_NET_PROFIT", "0.02"))

def get_open_exposures(db: Session) -> Dict[str, float]:
    cap = DEFAULT_CAPITAL
    if cap <= 0:
        cap = 100.0
    exposures: Dict[str, float] = {}
    return exposures

def consecutive_losses(db: Session, lookback: int = 50) -> int:
    stmt = select(models.PnL).order_by(desc(models.PnL.id)).limit(lookback)
    cnt = 0
    for row in db.execute(stmt).scalars().all():
        if row.realized is not None and row.realized < 0:
            cnt += 1
        else:
            break
    return cnt

def evaluate_and_publish(
    db: Session,
    symbol: str,
    tf_base: str,
    ts: int,
    direction: Literal["LONG","SHORT"],
    close: float,
    atr_val: float,
    fib_levels: Optional[Dict[str, float]],
    desired_leverage: float,
    risk: Literal["LOW","MED","HIGH"],
    capital: float,
    confidence: Optional[float] = None,
    margin_mode: Literal["ISOLATED","CROSS"] = "ISOLATED",
) -> Tuple[Optional[models.Signal], Optional[str]]:

    if consecutive_losses(db) >= int(os.getenv("MAX_CONSECUTIVE_LOSSES", "5")):
        return None, "cooldown_kill_switch_active"

    lev = leverage_for(desired_leverage, risk)
    prop: SignalProposal = build_proposal(
        symbol=symbol, tf_base=tf_base, ts=ts, direction=direction, close=close, atr_val=atr_val,
        fib_levels=fib_levels, lev=lev, risk=risk, margin_mode=margin_mode,
        validity_min=240, reentry_max=1, trailing_after_tp1=True
    )

    qty, risk_dollar = position_size(capital, risk, prop.levels.entry, prop.levels.sl)
    if qty <= 0 or risk_dollar <= 0:
        return None, "invalid_sizing"

    new_exposure_frac = risk_dollar / max(capital, 1e-9)
    reason = check_caps(get_open_exposures(db), new_exposure_frac, symbol, capital)
    if reason:
        return None, reason

    if confidence is not None:
        min_conf = float(os.getenv("CONFIDENCE_MIN", "0.55"))
        if confidence < min_conf:
            return None, f"low_confidence ({confidence:.2f} < {min_conf:.2f})"

    net_pct = expected_net_pct(
        direction=prop.direction,
        entry=prop.levels.entry,
        tp_targets=prop.levels.tp[:3],
        sl=prop.levels.sl,
        qty=qty,
        maker_first=True,
        fallback_taker=True,
        funding_minutes=float(prop.validity_min) * 0.5,
        funding_rate_hourly=0.0,
        tp_split=(0.3,0.4,0.3),
    )
    if net_pct < MIN_NET_PROFIT:
        return None, f"net_profit_below_threshold ({net_pct:.4f} < {MIN_NET_PROFIT:.4f})"

    liq = estimate_liquidation_price(prop.direction, prop.levels.entry, lev)
    if prop.direction == "LONG" and liq >= prop.levels.sl:
        return None, "liquidation_too_close_to_sl"
    if prop.direction == "SHORT" and liq <= prop.levels.sl:
        return None, "liquidation_too_close_to_sl"

    sig = models.Signal(
        id=str(uuid.uuid4()),
        symbol=prop.symbol,
        tf_base=prop.tf_base,
        ts=prop.ts,
        dir=prop.direction,
        entry=prop.levels.entry,
        tp=prop.levels.tp[:3],
        sl=prop.levels.sl,
        lev=lev,
        risk=prop.risk,
        margin_mode=prop.margin_mode,
        expected_net_pct=float(net_pct),
        confidence=confidence,
        model_ver=None,
        reason_discard=None,
        status="published",
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)

    # publish event to bus
    try:
        publish("signal_published", {
            "signal_id": sig.id,
            "symbol": sig.symbol,
            "dir": sig.dir,
            "entry": sig.entry,
            "sl": sig.sl,
            "tp": sig.tp,
            "lev": sig.lev,
            "expected_net_pct": sig.expected_net_pct,
        })
    except Exception:
        pass

    return sig, None
