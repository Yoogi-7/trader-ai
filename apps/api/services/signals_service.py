# apps/api/services/signals_service.py
# PL: Warstwa serwisowa do generacji/oceny/publikacji sygnałów (filtr ≥2%, capy, cooldown/kill-switch).
# EN: Service layer for generating/evaluating/publishing signals (>=2% net filter, caps, cooldown/kill-switch).

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

MIN_NET_PROFIT = float(os.getenv("MIN_NET_PROFIT", "0.02"))  # 2%

def get_open_exposures(db: Session) -> Dict[str, float]:
    """
    Approx exposure fraction by symbol = SUM(risk$)/capital.
    We don't have per-user capital here; treat capital as DEFAULT_CAPITAL for exposure normalization.
    """
    cap = DEFAULT_CAPITAL
    if cap <= 0:
        cap = 100.0
    exposures: Dict[str, float] = {}
    # Heuristic: treat each published signal's margin (qty * |entry-sl|) as risk$
    stmt = select(models.Signal).where(models.Signal.status == "published")
    for s in db.execute(stmt).scalars().all():
        margin = s.lev  # placeholder? we don't store qty/risk$ in DB
        # Without qty, we approximate exposure with lev*0 (not available). Better: store in meta later.
        # For now, skip exposure accumulation if not tracked:
        continue
    # As we cannot reconstruct risk$ reliably here, return empty (caps will be enforced per new exposure only).
    return exposures

def consecutive_losses(db: Session, lookback: int = 50) -> int:
    """
    Count consecutive losing signals from recent PnL rows.
    """
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
    """
    Returns (Signal, None) if published, else (None, discard_reason)
    """

    # Kill-switch / cooldown
    if consecutive_losses(db) >= int(os.getenv("MAX_CONSECUTIVE_LOSSES", "5")):
        return None, "cooldown_kill_switch_active"

    # Build proposal
    lev = leverage_for(desired_leverage, risk)
    prop: SignalProposal = build_proposal(
        symbol=symbol, tf_base=tf_base, ts=ts, direction=direction, close=close, atr_val=atr_val,
        fib_levels=fib_levels, lev=lev, risk=risk, margin_mode=margin_mode,
        validity_min=240, reentry_max=1, trailing_after_tp1=True
    )

    # Sizing
    qty, risk_dollar = position_size(capital, risk, prop.levels.entry, prop.levels.sl)
    if qty <= 0 or risk_dollar <= 0:
        return None, "invalid_sizing"

    # Exposure caps (approximation)
    new_exposure_frac = risk_dollar / max(capital, 1e-9)
    reason = check_caps(get_open_exposures(db), new_exposure_frac, symbol, capital)
    if reason:
        return None, reason

    # Confidence threshold (if provided)
    if confidence is not None:
        min_conf = float(os.getenv("CONFIDENCE_MIN", "0.55"))
        if confidence < min_conf:
            return None, f"low_confidence ({confidence:.2f} < {min_conf:.2f})"

    # ≥ 2% net after costs
    net_pct = expected_net_pct(
        direction=prop.direction,
        entry=prop.levels.entry,
        tp_targets=prop.levels.tp[:3],
        sl=prop.levels.sl,
        qty=qty,
        maker_first=True,
        fallback_taker=True,
        funding_minutes=float(prop.validity_min) * 0.5,  # conservative half-validity holding
        funding_rate_hourly=0.0,  # can be fed from data later
        tp_split=(0.3,0.4,0.3),
    )
    if net_pct < MIN_NET_PROFIT:
        return None, f"net_profit_below_threshold ({net_pct:.4f} < {MIN_NET_PROFIT:.4f})"

    # Estimate liquidation vs SL sanity check
    liq = estimate_liquidation_price(prop.direction, prop.levels.entry, lev)
    if prop.direction == "LONG" and liq >= prop.levels.sl:
        return None, "liquidation_too_close_to_sl"
    if prop.direction == "SHORT" and liq <= prop.levels.sl:
        return None, "liquidation_too_close_to_sl"

    # Persist signal
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
    return sig, None
