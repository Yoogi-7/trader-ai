# apps/ml/jobs/train.py
from __future__ import annotations
from celery import shared_task
from apps.api.db.session import SessionLocal
from apps.api.db.models import TrainingRun, Signal, OHLCV
from datetime import datetime
from sqlalchemy import select
from typing import Dict, Any, List
import time
import numpy as np

from apps.ml.drift import psi as psi_metric, ks as ks_metric
from apps.ml.backtest import BTParams, simulate_trade

def _load_bars(db, symbol: str, tf: str, start_ts: int, end_ts: int) -> List[dict]:
    q = (select(OHLCV)
         .where(OHLCV.symbol==symbol, OHLCV.tf==tf, OHLCV.ts>=start_ts, OHLCV.ts<=end_ts)
         .order_by(OHLCV.ts.asc()))
    rows = db.execute(q).scalars().all()
    return [{"ts":r.ts,"o":r.o,"h":r.h,"l":r.l,"c":r.c,"v":r.v} for r in rows]

def _wf_splits(n:int, folds:int=5) -> List[tuple[int,int,int,int]]:
    seg = n // folds
    out=[]
    for i in range(folds-1):
        tr_end = seg*(i+1)-1
        te_start = tr_end+1
        te_end = min(seg*(i+2)-1, n-1)
        out.append((0,tr_end,te_start,te_end))
    return out

@shared_task
def run_training(params: dict | None = None):
    params = params or {}
    db = SessionLocal()
    tr = TrainingRun(started_at=datetime.utcnow(), status="running", params_json=params)
    db.add(tr); db.commit(); db.refresh(tr)

    symbol = params.get("symbol","BTC/USDT")
    tf = params.get("tf","15m")
    start_ts = int(params.get("start_ts", 0))
    end_ts = int(params.get("end_ts", time.time()*1000))
    capital = float(params.get("capital", 100.0))
    risk = params.get("risk","LOW")

    bars = _load_bars(db, symbol, tf, start_ts, end_ts)
    if not bars:
        tr.status="error"; tr.finished_at=datetime.utcnow(); db.commit()
        return {"id": tr.id, "error":"no_bars"}

    ts_list = [b["ts"] for b in bars]
    folds = _wf_splits(len(ts_list), folds=params.get("n_folds",5))
    oos_metrics=[]
    # pseudo cechy do driftu: close
    closes = np.array([b["c"] for b in bars], dtype=float)

    for (a,b,c,d) in folds:
        tr_start, tr_end, te_start, te_end = ts_list[a], ts_list[b], ts_list[c], ts_list[d]
        # Sygnały
        train_sigs = list(db.execute(select(Signal).where(Signal.symbol==symbol, Signal.tf_base==tf, Signal.ts>=tr_start, Signal.ts<=tr_end, Signal.status=="published").order_by(Signal.ts.asc())).scalars().all())
        test_sigs  = list(db.execute(select(Signal).where(Signal.symbol==symbol, Signal.tf_base==tf, Signal.ts>=te_start, Signal.ts<=te_end, Signal.status=="published").order_by(Signal.ts.asc())).scalars().all())
        if not test_sigs: continue
        train_bars = [b for b in bars if tr_start <= b["ts"] <= tr_end]
        test_bars  = [b for b in bars if te_start <= b["ts"] <= te_end]
        p = BTParams(capital=capital, risk=risk, taker_only=True)

        eq = capital
        equity=[eq]; wins=[0,0,0]
        for s in test_sigs:
            risk_map = {"LOW":0.01,"MED":0.02,"HIGH":0.05}
            risk$ = capital * risk_map.get(risk, 0.01)
            dist = abs(s.entry - s.sl)
            if dist<=0: continue
            qty = risk$ / dist
            fut = [bb for bb in test_bars if bb["ts"] > s.ts]
            if not fut: continue
            trd = simulate_trade(fut, s.dir, s.entry, s.tp or [], s.sl, qty, p)
            eq += trd.pnl; equity.append(eq)
            if trd.hit_tp1: wins[0]+=1
            if trd.hit_tp2: wins[1]+=1
            if trd.hit_tp3: wins[2]+=1
        pnl_total = eq - capital
        peak = equity[0]; max_dd=0.0
        for e in equity: peak=max(peak,e); max_dd=max(max_dd,peak-e)
        hr1 = wins[0]/max(1,len(test_sigs))
        pf = (sum(max(0, equity[i]-equity[i-1]) for i in range(1,len(equity)))
              / max(1e-9, abs(sum(min(0, equity[i]-equity[i-1]) for i in range(1,len(equity))))))
        mar = (pnl_total/max_dd) if max_dd>0 else float("inf")
        oos_metrics.append({"hit_rate_tp1":hr1,"pf":pf,"mar":mar,"max_dd_pct": (max_dd/capital if capital>0 else 0.0)})

    def avg(k:str)->float: return float(sum(m.get(k,0.0) for m in oos_metrics)/max(1,len(oos_metrics)))
    # Drift PSI/KS między pierwszą i ostatnią częścią danych
    split = len(closes)//2
    psi_val = psi_metric(closes[:split], closes[split:]) if split>10 else 0.0
    ks_val = ks_metric(closes[:split], closes[split:]) if split>10 else 0.0

    metrics = {
        "ok": True, "folds": len(oos_metrics),
        "metrics_avg": {"hit_rate_tp1":avg("hit_rate_tp1"), "pf":avg("pf"), "mar":avg("mar"), "max_dd_pct":avg("max_dd_pct")},
        "drift": {"psi": psi_val, "ks": ks_val},
    }
    tr.metrics_json = metrics
    tr.status = "done"; tr.finished_at = datetime.utcnow()
    db.commit()
    return {"id": tr.id, "metrics": metrics}
