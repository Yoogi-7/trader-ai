import math

import pytest

from apps.ml.backtest import BTParams, simulate_trade


def _bar(ts: int, high: float, low: float, close: float) -> dict:
    return {"ts": ts, "h": high, "l": low, "c": close}


def test_multi_tp_partial_closes_all_targets():
    params = BTParams(
        capital=10_000,
        risk="MED",
        taker_only=False,
        slippage_bps=0.0,
        time_stop_min=10,
        trailing_after_tp1=True,
        trailing_offset_pct=0.01,
    )
    entry = 100.0
    tp = [110.0, 120.0, 130.0]
    sl = 90.0
    qty = 3.0
    bars = [
        _bar(0, 108.0, 95.0, 104.0),
        _bar(1, 111.0, 100.0, 110.0),
        _bar(2, 121.0, 110.0, 120.0),
        _bar(3, 131.0, 120.0, 128.0),
    ]

    result = simulate_trade(bars, "LONG", entry, tp, sl, qty, params)

    assert result.hit_tp1 and result.hit_tp2 and result.hit_tp3
    assert math.isclose(result.fee, 0.0, abs_tol=1e-9)
    expected_pnl = (tp[0] - entry) * (qty * params.tp_split[0])
    expected_pnl += (tp[1] - entry) * (qty * params.tp_split[1])
    expected_pnl += (tp[2] - entry) * (qty * params.tp_split[2])
    assert result.pnl == pytest.approx(expected_pnl, rel=1e-6)


def test_trailing_stop_activates_after_tp1():
    params = BTParams(
        capital=10_000,
        risk="MED",
        taker_only=False,
        slippage_bps=0.0,
        time_stop_min=10,
        trailing_after_tp1=True,
        trailing_offset_pct=0.02,
    )
    entry = 100.0
    tp = [105.0, 110.0, 120.0]
    sl = 90.0
    qty = 1.0
    bars = [
        _bar(0, 106.0, 99.0, 104.5),  # hits TP1
        _bar(1, 115.0, 104.0, 114.0),
        _bar(2, 114.0, 111.0, 112.0),  # trailing stop triggered
    ]

    result = simulate_trade(bars, "LONG", entry, tp, sl, qty, params)

    assert result.hit_tp1 and not result.hit_tp2
    trail_exit = 115.0 * (1 - params.trailing_offset_pct)
    assert result.exit == pytest.approx(trail_exit, rel=1e-6)
    assert result.pnl > (tp[0] - entry) * params.tp_split[0]
