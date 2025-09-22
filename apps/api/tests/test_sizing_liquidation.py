from trader_api.services.sizing import calc_qty

def test_min_notional_adjustment():
    q = calc_qty(100, 0.01, entry=100.0, sl=99.0, min_notional=5.0)
    assert q * 100.0 >= 5.0
