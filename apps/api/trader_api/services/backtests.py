# Minimalny backtester pod API (pełniejszy silnik w apps/ml).
from decimal import Decimal

def apply_funding(pnl: float, hrs: float, funding_bps_hour: float) -> float:
    return pnl - (abs(pnl) * (funding_bps_hour/10000.0) * hrs)

def equity_curve(start_capital: float, trades: list[dict]) -> list[float]:
    eq = [start_capital]
    cur = start_capital
    for t in trades:
        cur += float(Decimal(str(t["pnl"])))
        eq.append(cur)
    return eq
