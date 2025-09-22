
from celery import shared_task
from apps.api.db.session import SessionLocal
from apps.api.db.models import Backtest, BacktestTrade
from datetime import datetime
import time, random

@shared_task
def run_backtest(params: dict | None = None):
    db = SessionLocal()
    bt = Backtest(started_at=datetime.utcnow(), status="running", params_json=params or {})
    db.add(bt); db.commit(); db.refresh(bt)
    # Demo: create a few trades with PnL
    trades = []
    for i in range(5):
        entry = 60000 + random.uniform(-1000, 1000)
        exit = entry + random.uniform(-200, 400)
        fee = 2.0
        pnl = (exit - entry) - fee
        t = BacktestTrade(backtest_id=bt.id, symbol="BTCUSDT", entry_ts=int(time.time()*1000), exit_ts=int(time.time()*1000)+600000, entry=entry, exit=exit, fee=fee, pnl=pnl)
        db.add(t); trades.append(pnl)
    db.commit()
    bt.summary_json = {"equity_end": round(100 + sum(trades), 2), "hit_rate": round(random.uniform(0.55, 0.7), 2)}
    bt.finished_at = datetime.utcnow(); bt.status="done"
    db.commit()
    return {"id": bt.id, "summary": bt.summary_json}
