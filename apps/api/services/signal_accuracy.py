# apps/api/services/signal_accuracy.py
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.db import models


@dataclass
class PotentialAccuracy:
    score: int
    label: str
    components: Dict[str, float]
    sample_size: int
    regime_sample_size: int
    recent_sample_size: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "label": self.label,
            "components": self.components,
            "sample_size": self.sample_size,
            "regime_sample_size": self.regime_sample_size,
            "recent_sample_size": self.recent_sample_size,
        }


class SignalAccuracyEvaluator:
    """Estimate hit probability for a signal from historical performance."""

    def __init__(self, db: Session, window: int = 200):
        self._db = db
        self._window = max(10, window)
        self._history_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}

    # -------- Public API --------
    def score_signal(
        self,
        *,
        symbol: str,
        direction: str,
        market_regime: Optional[str],
        confidence: Optional[float],
        expected_net_pct: float,
    ) -> PotentialAccuracy:
        direction_norm = direction.upper()
        stats = self._history_stats(symbol, direction_norm)

        base_rate = stats["base_win_rate"]
        base_sample = stats["sample_size"]
        recent_rate = stats["recent_win_rate"]
        recent_sample = stats["recent_sample_size"]

        regime_name = (market_regime or "unknown").lower()
        regime_stats = stats["regime_win_rates"].get(regime_name)
        if regime_stats:
            regime_rate = regime_stats["win_rate"]
            regime_sample = regime_stats["sample_size"]
        else:
            regime_rate = base_rate
            regime_sample = base_sample

        history_component = self._shrink_towards(0.5, base_rate, base_sample)
        regime_component = self._shrink_towards(history_component, regime_rate, regime_sample)
        recent_component = self._shrink_towards(history_component, recent_rate, recent_sample)

        confidence_component = self._sanitize_confidence(confidence)
        net_component = self._normalize_expected_net(expected_net_pct)

        score = (
            0.35 * history_component
            + 0.2 * regime_component
            + 0.3 * confidence_component
            + 0.1 * recent_component
            + 0.05 * net_component
        )
        score = max(0.0, min(1.0, score))
        label = self._label_for_score(score)

        components = {
            "history": float(history_component),
            "regime": float(regime_component),
            "confidence": float(confidence_component),
            "recent": float(recent_component),
            "expected_net": float(net_component),
            "history_raw": float(base_rate),
            "regime_raw": float(regime_rate),
            "recent_raw": float(recent_rate),
        }

        return PotentialAccuracy(
            score=int(round(score * 100)),
            label=label,
            components=components,
            sample_size=base_sample,
            regime_sample_size=regime_sample,
            recent_sample_size=recent_sample,
        )

    def score_existing_signal(self, signal: models.Signal) -> PotentialAccuracy:
        direction = (signal.dir or "").upper() or "LONG"
        market_regime = infer_market_regime(signal)
        confidence = float(signal.confidence) if signal.confidence is not None else None
        expected_net = float(signal.expected_net_pct or 0.0)
        return self.score_signal(
            symbol=signal.symbol,
            direction=direction,
            market_regime=market_regime,
            confidence=confidence,
            expected_net_pct=expected_net,
        )

    # -------- Internals --------
    def _history_stats(self, symbol: str, direction: str) -> Dict[str, Any]:
        key = (symbol, direction.upper())
        if key in self._history_cache:
            return self._history_cache[key]

        subq = (
            select(models.Signal.id)
            .where(models.Signal.symbol == symbol)
            .where(models.Signal.dir == direction.upper())
            .where(models.Signal.status == "published")
            .order_by(models.Signal.ts.desc())
            .limit(self._window)
            .subquery()
        )

        stmt = (
            select(models.Signal, models.PnL.realized)
            .select_from(models.Signal)
            .join(subq, models.Signal.id == subq.c.id)
            .outerjoin(models.PnL, models.PnL.signal_id == models.Signal.id)
            .order_by(models.Signal.ts.desc())
        )
        rows = self._db.execute(stmt).all()

        per_signal: Dict[str, Tuple[models.Signal, Optional[float]]] = {}
        for row in rows:
            sig: models.Signal = row[0]
            realized = row[1]
            existing = per_signal.get(sig.id)
            if existing is None or (existing[1] is None and realized is not None):
                per_signal[sig.id] = (sig, realized)

        ordered = list(per_signal.values())
        ordered.sort(key=lambda item: item[0].ts, reverse=True)

        wins = 0
        counted = 0
        regime_counters: Dict[str, Dict[str, float]] = {}
        recent_flags = []

        for idx, (sig, realized) in enumerate(ordered):
            if realized is None:
                continue
            counted += 1
            if realized > 0:
                wins += 1
                recent_flags.append(1)
            else:
                recent_flags.append(0)
            regime = infer_market_regime(sig) or "unknown"
            regime_key = regime.lower()
            stats = regime_counters.setdefault(regime_key, {"wins": 0.0, "sample": 0.0})
            stats["sample"] += 1
            if realized > 0:
                stats["wins"] += 1

        # limit recent sample to latest 5 closed trades
        recent_flags = recent_flags[:5]
        recent_sample = len(recent_flags)
        recent_win_rate = (sum(recent_flags) / recent_sample) if recent_sample else 0.5

        base_win_rate = (wins / counted) if counted else 0.5

        regime_win_rates: Dict[str, Dict[str, float]] = {}
        for regime_key, stats in regime_counters.items():
            sample = int(stats["sample"])
            win_rate = (stats["wins"] / sample) if sample else 0.5
            regime_win_rates[regime_key] = {"win_rate": win_rate, "sample_size": sample}

        payload = {
            "base_win_rate": base_win_rate,
            "sample_size": counted,
            "recent_win_rate": recent_win_rate,
            "recent_sample_size": recent_sample,
            "regime_win_rates": regime_win_rates,
        }
        self._history_cache[key] = payload
        return payload

    @staticmethod
    def _sanitize_confidence(value: Optional[float]) -> float:
        if value is None or not isfinite(value):
            return 0.5
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _normalize_expected_net(expected_net_pct: float) -> float:
        try:
            value = float(expected_net_pct)
        except (TypeError, ValueError):
            return 0.5
        if not isfinite(value):
            return 0.5
        # 5%+ expected net is treated as top quartile quality.
        normalized = value / 0.05
        normalized = max(0.0, min(1.2, normalized))
        return max(0.0, min(1.0, normalized))

    @staticmethod
    def _shrink_towards(target: float, value: float, sample_size: int, reference: int = 30) -> float:
        sample = max(0, sample_size)
        strength = min(sample / max(reference, 1), 1.0)
        return target * (1.0 - strength) + value * strength

    @staticmethod
    def _label_for_score(score: float) -> str:
        pct = score * 100.0
        if pct >= 85.0:
            return "very_high"
        if pct >= 70.0:
            return "high"
        if pct >= 55.0:
            return "medium"
        if pct >= 40.0:
            return "low"
        return "very_low"


def infer_market_regime(signal: models.Signal) -> Optional[str]:
    direct = getattr(signal, "market_regime", None)
    if isinstance(direct, str) and direct:
        return direct
    model_ver = getattr(signal, "model_ver", None)
    if isinstance(model_ver, str) and "|" in model_ver:
        suffix = model_ver.split("|", 1)[1]
        if suffix:
            return suffix
    summary = getattr(signal, "ai_summary", None) or ""
    tokens = summary.split()
    for idx, token in enumerate(tokens):
        if token.lower() == "regime" and idx + 1 < len(tokens):
            return tokens[idx + 1]
    return None
