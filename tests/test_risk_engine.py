# tests/test_risk_engine.py
from __future__ import annotations
import os

from apps.ml.risk.engine import apply_caps_and_sizing, quality_filter_2pct

def test_sizing_min_notional_and_lot():
    os.environ["EXCH_MIN_NOTIONAL"] = "10"
    os.environ["EXCH_LOT_STEP"] = "0.001"
    res = apply_caps_and_sizing(
        symbol="BTCUSDT", side="long", entry=100.0, sl=99.0,
        capital_usd=100.0, profile_name="LOW",
        existing_parallel_positions=0, current_exposure_by_symbol={}
    )
    # ryzyko 0.5% * 100$ = 0.5$; dist=1$; lev<=5 => qty~(0.5/1)*5/100=0.025
    # exposure=2.5$, poniżej min_notional=10$ => block
    assert res.qty == 0.0 and res.reason_block == "below_min_notional"

def test_parallel_positions_cap():
    os.environ["RISK_LOW_MAX_PARALLEL"] = "1"
    res = apply_caps_and_sizing(
        symbol="ETHUSDT", side="long", entry=100.0, sl=98.0,
        capital_usd=1000.0, profile_name="LOW",
        existing_parallel_positions=1, current_exposure_by_symbol={}
    )
    assert res.reason_block == "too_many_parallel_positions"

def test_btc_eth_corr_cap():
    os.environ["RISK_BTC_ETH_CORR_CAP_PCT"] = "20"
    res = apply_caps_and_sizing(
        symbol="ETHUSDT", side="long", entry=100.0, sl=95.0,
        capital_usd=1000.0, profile_name="MED",
        existing_parallel_positions=0,
        current_exposure_by_symbol={"BTCUSDT": 150.0}
    )
    # cap 20% * 1000 = 200$; jeśli ETH dorzuci >50$, powinno ściąć/odrzucić
    # sizing MED: risk=1%=>10$, dist=5$, lev<=10 => qty ~ (10/5)*10/100=0.2, exp=20$
    # 150 + 20 = 170 <= 200 -> powinno przejść (brak block)
    assert res.reason_block is None
    # teraz BTC 190$, ETH 20$ => 210 > 200 -> block
    res2 = apply_caps_and_sizing(
        symbol="ETHUSDT", side="long", entry=100.0, sl=95.0,
        capital_usd=1000.0, profile_name="MED",
        existing_parallel_positions=0,
        current_exposure_by_symbol={"BTCUSDT": 190.0}
    )
    assert res2.reason_block == "btc_eth_corr_cap"

def test_quality_filter_2pct():
    os.environ["MAKER_FEE_BPS"] = "1"
    os.environ["TAKER_FEE_BPS"] = "5"
    os.environ["DEFAULT_SLIPPAGE_BPS"] = "5"
    ok, net = quality_filter_2pct(100.0, 103.0, maker_first=True, holding_hours=12.0)
    assert ok and net > 2.0
