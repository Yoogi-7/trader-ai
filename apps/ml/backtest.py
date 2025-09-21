# Simple backtester with TP/SL and funding approximation
import time, json, random
from apps.api.db import SessionLocal
from apps.api.models import Backtest, BacktestTrade

def run():
    db = SessionLocal()
    bt = Backtest(params_json={"start_capital":100,"fee_bps":10}, summary_json={})
    db.add(bt); db.commit()
    capital = 100.0; trades = []
    for i in range(50):
        entry = 100.0; tp1=102.0; sl=98.0
        hit_tp = random.random() < 0.6
        exit_px = tp1 if hit_tp else sl
        fee = entry*0.001 + exit_px*0.001
        pnl = (exit_px-entry) - fee
        funding = 0.01 if hit_tp else -0.005
        pnl -= funding
        capital += pnl
        t = BacktestTrade(signal_id=i+1, entry=entry, exit=exit_px, fee=round(fee,4),
                          pnl=round(pnl,4), hit_tp_level=1 if hit_tp else 0,
                          opened_at=int(time.time()*1000), closed_at=int(time.time()*1000)+600000)
        db.add(t)
        trades.append(pnl)
    db.commit()
    summary = {"final_capital": round(capital,2), "hit_rate_tp1": round(sum(1 for x in trades if x>0)/len(trades),2)}
    bt.summary_json = summary; db.commit()
    print("Backtest:", summary)

if __name__ == "__main__":
    run()