
from apps.api.schemas import BacktestRequest
from apps.api.tools.backtester import run_backtest_sync

if __name__ == "__main__":
    req = BacktestRequest(capital=100.0, risk_profile="LOW", pairs=["BTCUSDT","ETHUSDT"])
    print(run_backtest_sync(req))
