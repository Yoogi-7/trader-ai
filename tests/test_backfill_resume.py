
from apps.ml.jobs.backfill import run_backfill

def test_backfill_smoke():
    res = run_backfill.apply(kwargs={"pairs":["BTCUSDT"], "tf":"1m"}).get(timeout=10)
    assert res["ok"] == True
