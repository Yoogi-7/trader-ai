# apps/api/services/signals_service.py
from __future__ import annotations
import os, uuid, time
from typing import Optional, Dict, Any, Tuple, Literal
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from apps.api.db import models
from apps.ml.signal_engine import atr_levels, fib_adjust, Levels
from apps.ml.feature_pipeline import build_mtf_context, multi_tf_confirm
from apps.ml.models.stacking import StackingEnsemble
from apps.ml.models.conformal import InductiveConformal

FEE_MAKER = float(os.getenv("FEE_MAKER", "0.0002"))
FEE_TAKER = float(os.getenv("FEE_TAKER", "0.0005"))
SLIPPAGE_BPS = float(os.getenv("SLIPPAGE_BPS", "10"))
MIN_NET = float(os.getenv("MIN_NET_PROFIT", "0.02"))
CONF_MIN = float(os.getenv("CONFIDENCE_MIN", "0.55"))

def _side_mult(direction: str) -> int:
    return 1 if direction=="LONG" else -1

def _expected_net_pct(direction: str, entry: float, tp: list[float], sl: float, qty: float, funding_rate_hourly: float=0.0, validity_min:int=240) -> float:
    # konserwatywnie: ważymy zysk TP1/2/3 wagami 0.3/0.4/0.3, koszt: fee open+close (taker), slippage bps, funding
    w=(0.3,0.4,0.3); d=_side_mult(direction)
    pnl = 0.0
    for wi,ti in zip(w,tp[:3]):
        pnl += wi * (ti - entry)*d * qty
    fee = (entry*qty + (tp[-1]*qty))*(FEE_TAKER)  # worst-case
    slip = entry*qty*(SLIPPAGE_BPS/10_000.0)
    funding = entry*qty*funding_rate_hourly*(validity_min/60.0)
    margin = qty*abs(entry-sl)
    if margin<=0: return -1.0
    return float((pnl - fee - slip - funding)/margin)

def _position_size(capital: float, risk_per_trade: float, entry: float, sl: float, min_notional: float=5.0) -> tuple[float,float]:
    risk_usd = capital * risk_per_trade
    if risk_usd<=0 or abs(entry-sl)<=0: return 0.0, 0.0
    qty = risk_usd / abs(entry-sl)
    if entry*qty < min_notional:
        qty = min_notional/entry
    return float(qty), float(risk_usd)

def evaluate_signal(
    db: Session,
    symbol: str,
    tf_base: str,
    ts: int,
    direction: Literal["LONG","SHORT"],
    close: float,
    atr: float,
    fibo: Optional[Dict[str,float]],
    risk_profile: Literal["LOW","MED","HIGH"],
    capital: float,
    funding_rate_hourly: float = 0.0,
) -> Tuple[Optional[models.Signal], Optional[str]]:
    # Multi-TF confirm
    ctx = build_mtf_context(db, symbol, ts)
    if not multi_tf_confirm(ctx, direction, slope_thr=0.0, mom_thr=0.0):
        return None, "mtf_confirm_failed"

    # Levels
    lv = atr_levels(close, atr, direction)
    lv = fib_adjust(lv, fibo)

    # Sizing
    risk_map = {"LOW":0.01, "MED":0.02, "HIGH":0.05}
    qty, risk_usd = _position_size(capital, risk_map[risk_profile], lv.entry, lv.sl)
    if qty<=0: return None, "invalid_sizing"

    # Ensemble + confidence (tu: przykładowa ekstrakcja cech – do faktycznego feeder'a pod modele)
    import numpy as np
    X_tab = np.array([[atr, ctx.get("1h_slope",0.0), ctx.get("4h_slope",0.0), ctx.get("1h_mom",0.0), ctx.get("4h_mom",0.0)]], dtype=float)
    X_seq = np.tile(np.array([[close, atr]], dtype=float), (20,1))[None, ...]  # (1,T,F) — placeholder

    ens = StackingEnsemble()
    # Uwaga: tu w realu należałoby wczytać dopasowane modele z registry; demonstracyjnie dopasujemy szybko na pseudo-danych:
    y_demo = np.array([0,1,1,0,1,0,1,1,0,1], dtype=int)
    ens.fit(np.tile(X_tab, (len(y_demo),1)), np.tile(X_seq, (len(y_demo),1,1)), y_demo)
    p = ens.predict_proba(X_tab, X_seq)

    icp = InductiveConformal()
    icp.fit(y_demo, np.tile(p, (len(y_demo),1)))
    conf = float(icp.confidence(p)[0])
    if conf < CONF_MIN:
        return None, f"low_confidence ({conf:.2f}<{CONF_MIN:.2f})"

    # ≥ 2% netto
    net = _expected_net_pct(direction, lv.entry, lv.tp, lv.sl, qty, funding_rate_hourly)
    if net < MIN_NET:
        return None, f"net_profit_below_threshold ({net:.4f}<{MIN_NET:.4f})"

    # Persist
    sig = models.Signal(
        id=str(uuid.uuid4()),
        symbol=symbol,
        tf_base=tf_base,
        ts=ts,
        dir=direction,
        entry=lv.entry,
        tp=lv.tp[:3],
        sl=lv.sl,
        lev=3,
        risk=risk_map[risk_profile],
        margin_mode="ISOLATED",
        expected_net_pct=float(net),
        confidence=conf,
        model_ver="ensemble-demo",
        reason_discard=None,
        status="published",
    )
    db.add(sig); db.commit(); db.refresh(sig)
    return sig, None
