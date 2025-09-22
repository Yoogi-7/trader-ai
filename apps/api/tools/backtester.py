
from __future__ import annotations
from typing import Dict, Any, List
import math

def run_backtest_sync(req) -> Dict[str, Any]:
    # minimalny mock backtestu – w prawdziwej wersji wywołujemy silnik z apps.ml
    capital = float(req.capital)
    hit_rate = 0.58  # zakładamy OOS>55%
    pf = 1.35
    mar = 0.8
    dd = 0.15
    # PnL od 100$
    start = 100.0
    pnl = start * (pf - 1.0) * 0.5  # czysto symboliczne
    return {
        "start_capital_100": start,
        "pnl_on_100": round(pnl, 2),
        "hit_rate_tp1_oos": hit_rate,
        "profit_factor": pf,
        "mar": mar,
        "max_dd": dd,
    }
