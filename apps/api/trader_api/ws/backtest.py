from fastapi import APIRouter
from ..schemas import BacktestRequest
from ..services.backtests import equity_curve

router = APIRouter(prefix="/backtest", tags=["backtest"])

@router.post("/run")
def run_backtest(req: BacktestRequest):
    # stub — realny backtester w apps/ml; tu trzymamy interfejs i krótką odpowiedź
    trades = [{"pnl": 2.5}, {"pnl": -1.1}, {"pnl": 3.0}]
    eq = equity_curve(req.capital, trades)
    return {"summary":{"start_capital": req.capital, "end_capital": eq[-1]}, "equity": eq}
