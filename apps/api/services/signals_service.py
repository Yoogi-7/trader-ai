# apps/api/services/signals_service.py
from __future__ import annotations
import os, uuid, time
from typing import Optional, Dict, Any, Tuple, Literal
from math import isfinite
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from apps.api.db import models
from apps.ml.signal_engine import atr_levels, fib_adjust, Levels
from apps.ml.risk import dynamic_risk_fraction, position_size
from apps.ml.market_regime import (
    detect_market_regime,
    REGIME_TREND_UP,
    REGIME_TREND_DOWN,
    REGIME_SIDEWAYS,
    REGIME_HIGH_VOL,
)
from apps.ml.feature_pipeline import build_mtf_context, multi_tf_confirm
from apps.ml.models.stacking import StackingEnsemble
from apps.ml.models.conformal import InductiveConformal
from apps.ml.sentiment_plugin import load_provider as load_sentiment_provider
from apps.api.services.signal_accuracy import SignalAccuracyEvaluator

FEE_MAKER = float(os.getenv("FEE_MAKER", "0.0002"))
FEE_TAKER = float(os.getenv("FEE_TAKER", "0.0005"))
SLIPPAGE_BPS = float(os.getenv("SLIPPAGE_BPS", "10"))
MIN_NET = float(os.getenv("MIN_NET_PROFIT", "0.02"))
CONF_MIN = float(os.getenv("CONFIDENCE_MIN", "0.55"))


def _format_pct(value: float) -> str:
    return f"{value:.1f}%"


def generate_ai_summary(
    *,
    symbol: str,
    tf_base: str,
    direction: str,
    entry: float,
    tp: list[float] | None,
    sl: float,
    expected_net_pct: float,
    confidence_rating: int | None,
    market_regime: str,
    sentiment_rating: int | None,
    potential_accuracy_score: int | None = None,
    potential_accuracy_label: str | None = None,
) -> str:
    direction_text = "trend wzrostowy" if direction.upper() == "LONG" else "trend spadkowy"
    tf_label = tf_base.upper()
    tp_price = tp[0] if tp else entry
    tp_pct = ((tp_price - entry) / entry * 100.0) if direction.upper() == "LONG" else ((entry - tp_price) / entry * 100.0)
    sl_pct = ((entry - sl) / entry * 100.0) if direction.upper() == "LONG" else ((sl - entry) / entry * 100.0)
    summary_parts = [
        f"AI znalazło {direction_text} na {tf_label}",
        f"→ {direction.upper()} {symbol}",
        f"TP { _format_pct(tp_pct) }",
        f"SL { _format_pct(abs(sl_pct)) }",
        f"Net { _format_pct(expected_net_pct * 100.0) }",
    ]
    if confidence_rating is not None:
        summary_parts.append(f"rating {confidence_rating}/100")
    summary_parts.append(f"regime {market_regime}")
    if sentiment_rating is not None:
        summary_parts.append(f"sentiment {sentiment_rating}/100")
    if potential_accuracy_score is not None:
        if potential_accuracy_label:
            summary_parts.append(f"acc {potential_accuracy_score}/100 {potential_accuracy_label}")
        else:
            summary_parts.append(f"acc {potential_accuracy_score}/100")
    return " ".join(summary_parts)

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


def _regime_fraction_multiplier(regime: str, direction: str) -> float:
    if regime == REGIME_TREND_UP:
        return 1.25 if direction == "LONG" else 0.6
    if regime == REGIME_TREND_DOWN:
        return 1.25 if direction == "SHORT" else 0.6
    if regime == REGIME_SIDEWAYS:
        return 0.7
    if regime == REGIME_HIGH_VOL:
        return 0.5
    return 1.0


def _regime_tp_scale(regime: str, direction: str) -> float:
    if regime == REGIME_TREND_UP:
        return 1.15 if direction == "LONG" else 0.9
    if regime == REGIME_TREND_DOWN:
        return 1.15 if direction == "SHORT" else 0.9
    if regime == REGIME_HIGH_VOL:
        return 1.3
    if regime == REGIME_SIDEWAYS:
        return 0.75
    return 1.0


def _scale_targets(entry: float, targets: list[float], scale: float) -> list[float]:
    if not targets or scale == 1.0:
        return targets
    scaled = []
    for t in targets:
        delta = t - entry
        scaled.append(entry + delta * scale)
    return scaled

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
    max_allocation_pct: Optional[float] = None,
) -> Tuple[Optional[models.Signal], Optional[str]]:
    # Multi-TF confirm
    ctx = build_mtf_context(db, symbol, ts)
    if not multi_tf_confirm(ctx, direction, slope_thr=0.0, mom_thr=0.0):
        return None, "mtf_confirm_failed"

    # Levels
    lv = atr_levels(close, atr, direction)
    lv = fib_adjust(lv, fibo)
    market_regime = detect_market_regime(close, atr, ctx)

    # Sizing
    risk_map = {"LOW":0.01, "MED":0.02, "HIGH":0.05}
    base_fraction = risk_map[risk_profile]
    volatility_ratio = abs(atr / close) if close else 0.0
    max_fraction = None
    if max_allocation_pct is not None and max_allocation_pct > 0:
        max_fraction = min(max_allocation_pct, 1.0)
    dynamic_fraction = dynamic_risk_fraction(
        base_fraction=base_fraction,
        volatility_ratio=volatility_ratio,
        max_portfolio_fraction=max_fraction,
    )

    fraction_multiplier = _regime_fraction_multiplier(market_regime, direction)
    dynamic_fraction *= fraction_multiplier
    if max_fraction is not None:
        dynamic_fraction = min(dynamic_fraction, max_fraction)
    dynamic_fraction = max(dynamic_fraction, base_fraction * 0.25)

    tp_scale = _regime_tp_scale(market_regime, direction)
    lv.tp = _scale_targets(lv.entry, lv.tp[:3] if lv.tp else [], tp_scale)

    # Sentiment bridge
    sentiment_provider = load_sentiment_provider()
    sentiment_score = sentiment_provider.get_score(symbol, ts)
    sentiment_rating = int(round((sentiment_score + 1.0) * 50.0))
    sentiment_rating = max(0, min(100, sentiment_rating))
    sentiment_multiplier = 1.0
    if sentiment_score >= 0.5 and direction == "LONG":
        sentiment_multiplier = 1.1
    elif sentiment_score <= -0.5 and direction == "SHORT":
        sentiment_multiplier = 1.1
    elif sentiment_score <= -0.5 and direction == "LONG":
        sentiment_multiplier = 0.75
    elif sentiment_score >= 0.5 and direction == "SHORT":
        sentiment_multiplier = 0.75
    dynamic_fraction *= sentiment_multiplier
    if max_fraction is not None:
        dynamic_fraction = min(dynamic_fraction, max_fraction)
    dynamic_fraction = max(dynamic_fraction, base_fraction * 0.25)

    qty, risk_usd = position_size(
        capital,
        risk_profile,
        lv.entry,
        lv.sl,
        risk_fraction_override=dynamic_fraction,
    )
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

    rating_raw = int(round(conf * 100.0))
    confidence_rating = int(min(100, max(1, rating_raw))) if isfinite(conf) else None

    # ≥ 2% netto
    net = _expected_net_pct(direction, lv.entry, lv.tp, lv.sl, qty, funding_rate_hourly)
    if net < MIN_NET:
        return None, f"net_profit_below_threshold ({net:.4f}<{MIN_NET:.4f})"

    accuracy_evaluator = SignalAccuracyEvaluator(db)
    potential_accuracy = accuracy_evaluator.score_signal(
        symbol=symbol,
        direction=direction,
        market_regime=market_regime,
        confidence=conf,
        expected_net_pct=float(net),
    )
    potential_accuracy_dict = potential_accuracy.as_dict()

    # Persist
    summary_text = generate_ai_summary(
        symbol=symbol,
        tf_base=tf_base,
        direction=direction,
        entry=lv.entry,
        tp=lv.tp[:3] if lv.tp else None,
        sl=lv.sl,
        expected_net_pct=float(net),
        confidence_rating=confidence_rating,
        market_regime=market_regime,
        sentiment_rating=sentiment_rating,
        potential_accuracy_score=potential_accuracy_dict["score"],
        potential_accuracy_label=potential_accuracy_dict["label"],
    )

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
        risk=f"{dynamic_fraction:.4f}",
        margin_mode="ISOLATED",
        expected_net_pct=float(net),
        confidence=conf,
        model_ver=f"ensemble-demo|{market_regime}",
        reason_discard=None,
        status="published",
        ai_summary=summary_text,
    )
    db.add(sig); db.commit(); db.refresh(sig)
    if confidence_rating is not None:
        sig.__dict__["confidence_rating"] = confidence_rating  # type: ignore[attr-defined]
    sig.__dict__["market_regime"] = market_regime  # type: ignore[attr-defined]
    sig.__dict__["sentiment_rating"] = sentiment_rating  # type: ignore[attr-defined]
    sig.__dict__["potential_accuracy"] = potential_accuracy_dict  # type: ignore[attr-defined]
    sig.__dict__["potential_accuracy_score"] = potential_accuracy_dict["score"]  # type: ignore[attr-defined]
    return sig, None
