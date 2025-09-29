import time

from apps.api.db import models
from apps.api.db.session import SessionLocal
from apps.api.services.signal_accuracy import SignalAccuracyEvaluator


def _now_ms() -> int:
    return int(time.time() * 1000)


def _reset_tables(db):
    db.query(models.PnL).delete()
    db.query(models.Signal).delete()
    db.commit()


def test_signal_accuracy_benefits_from_positive_history():
    with SessionLocal() as db:
        _reset_tables(db)
        base_ts = _now_ms()
        realized_outcomes = [0.04, 0.03, -0.02, 0.05, 0.06]
        for idx, realized in enumerate(realized_outcomes):
            sig = models.Signal(
                id=f"hist-{idx}",
                symbol="BTCUSDT",
                tf_base="15m",
                ts=base_ts - idx * 60000,
                dir="LONG",
                entry=20000.0,
                tp=[20500.0],
                sl=19500.0,
                lev=3.0,
                risk="LOW",
                margin_mode="ISOLATED",
                expected_net_pct=0.025,
                confidence=0.65,
                model_ver="ensemble-demo|trend_up" if idx % 2 == 0 else "ensemble-demo|sideways",
                status="published",
            )
            db.add(sig)
            db.add(models.PnL(signal_id=sig.id, realized=realized))
        db.commit()

        evaluator = SignalAccuracyEvaluator(db)
        result = evaluator.score_signal(
            symbol="BTCUSDT",
            direction="LONG",
            market_regime="trend_up",
            confidence=0.8,
            expected_net_pct=0.03,
        )

        assert result.sample_size == len(realized_outcomes)
        assert result.label in {"high", "very_high"}
        assert result.score >= 65


def test_signal_accuracy_defaults_when_history_missing():
    with SessionLocal() as db:
        _reset_tables(db)

        evaluator = SignalAccuracyEvaluator(db)
        result = evaluator.score_signal(
            symbol="ETHUSDT",
            direction="SHORT",
            market_regime=None,
            confidence=None,
            expected_net_pct=0.02,
        )

        assert 40 <= result.score <= 60
        assert result.label in {"low", "medium", "very_low"}
