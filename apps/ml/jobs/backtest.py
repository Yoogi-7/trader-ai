# apps/ml/jobs/backtest.py
from __future__ import annotations
from celery import shared_task
from apps.api.db.session import SessionLocal
from apps.api.db.models import Backtest, BacktestTrade, Signal, OHLCV
from typing import Dict, Any, List
from sqlalchemy import select
from apps.ml.backtest import BTParams, simulate_trade
import time


def _now_ms() -> int:
    return int(time.time() * 1000)

def _load_bars(db, symbol: str, tf: str, start_ts: int, end_ts: int) -> List[dict]:
    q = (select(OHLCV)
         .where(OHLCV.symbol==symbol, OHLCV.tf==tf, OHLCV.ts>=start_ts, OHLCV.ts<=end_ts)
         .order_by(OHLCV.ts.asc()))
    rows = db.execute(q).scalars().all()
    return [{"ts":r.ts,"o":r.o,"h":r.h,"l":r.l,"c":r.c,"v":r.v} for r in rows]

@shared_task
def run_backtest(params: dict | None = None):
    params = params or {}
    db = SessionLocal()
    bt = Backtest(started_at=_now_ms(), status="running", params_json=params)
    db.add(bt); db.commit(); db.refresh(bt)

    symbol = params.get("symbol","BTC/USDT")
    tf = params.get("tf","15m")
    start_ts = int(params.get("start_ts", 0))
    end_ts = int(params.get("end_ts", time.time()*1000))
    capital = float(params.get("capital", 100.0))
    risk = params.get("risk","LOW")
    funding_rate_hourly = float(params.get("funding_rate_hourly", 0.0))
    time_stop_min = int(params.get("time_stop_min", 240))
    slippage_bps = float(params.get("slippage_bps", 10.0))
    taker_only = bool(params.get("taker_only", True))
    trailing_offset_pct = float(params.get("trailing_offset_pct", 0.002))

    # ładujemy sygnały
    s_q = (select(Signal)
           .where(Signal.symbol==symbol, Signal.tf_base==tf, Signal.ts>=start_ts, Signal.ts<=end_ts, Signal.status=="published")
           .order_by(Signal.ts.asc()))
    signals = list(db.execute(s_q).scalars().all())
    if not signals:
        bt.status = "error"
        bt.finished_at = _now_ms()
        db.commit()
        return {"id": bt.id, "error": "no_signals_in_range"}

    bars = _load_bars(db, symbol, tf, start_ts, end_ts)
    p = BTParams(
        capital=capital,
        risk=risk,
        funding_rate_hourly=funding_rate_hourly,
        time_stop_min=time_stop_min,
        slippage_bps=slippage_bps,
        taker_only=taker_only,
        trailing_offset_pct=trailing_offset_pct,
    )

    eq = capital
    equity = [eq]
    wins = [0,0,0]
    for s in signals:
        # qty zgodnie z risk_usd / dist(SL)
        risk_map = {"LOW":0.01,"MED":0.02,"HIGH":0.05}
        risk_fraction = None
        if isinstance(s.risk, str):
            if s.risk in risk_map:
                risk_fraction = risk_map[s.risk]
            else:
                try:
                    risk_fraction = float(s.risk)
                except ValueError:
                    risk_fraction = None
        elif isinstance(s.risk, (int, float)):
            risk_fraction = float(s.risk)
        if risk_fraction is None:
            risk_fraction = risk_map.get("LOW", 0.01)
        risk_amount = capital * risk_fraction
        dist = abs(s.entry - s.sl)
        if dist<=0: continue
        qty = risk_amount / dist

        fut = [b for b in bars if b["ts"] > s.ts]
        if not fut: continue
        tr = simulate_trade(fut, s.dir, s.entry, s.tp or [], s.sl, qty, p)
        db.add(BacktestTrade(backtest_id=bt.id, symbol=s.symbol, entry_ts=tr.entry_ts, exit_ts=tr.exit_ts, entry=tr.entry, exit=tr.exit, fee=tr.fee, pnl=tr.pnl))
        eq += tr.pnl
        equity.append(eq)
        if tr.hit_tp1: wins[0]+=1
        if tr.hit_tp2: wins[1]+=1
        if tr.hit_tp3: wins[2]+=1

    pnl_total = eq - capital
    # max DD
    peak = equity[0]
    max_dd = 0.0
    for e in equity:
        peak = max(peak, e)
        max_dd = max(max_dd, peak - e)
    max_dd_pct = (max_dd / capital) if capital>0 else 0.0
    pf = (sum(max(0,x) for x in [t.pnl for t in db.query(BacktestTrade).filter(BacktestTrade.backtest_id==bt.id).all()])
          / max(1e-9, abs(sum(min(0,x) for x in [t.pnl for t in db.query(BacktestTrade).filter(BacktestTrade.backtest_id==bt.id).all()]))))
    mar = (pnl_total / max_dd) if max_dd>0 else float("inf")
    trades_n = db.query(BacktestTrade).filter(BacktestTrade.backtest_id==bt.id).count()
    hr1 = wins[0] / max(1, trades_n)
    hr2 = wins[1] / max(1, trades_n)
    hr3 = wins[2] / max(1, trades_n)

    bt.summary_json = {
        "equity_curve": equity,
        "pnl_total": pnl_total,
        "max_dd": max_dd,
        "max_dd_pct": max_dd_pct,
        "pf": pf, "mar": mar,
        "hit_rate_tp1": hr1, "hit_rate_tp2": hr2, "hit_rate_tp3": hr3,
        "trades": trades_n,
    }
    bt.finished_at = _now_ms()
    bt.status = "done"
    db.commit()
    return {"id": bt.id, "summary": bt.summary_json}
