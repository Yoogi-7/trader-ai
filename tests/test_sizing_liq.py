
from apps.api.tools.sizing import position_size, liquidation_price

def test_sizing_and_liq():
    qty = position_size(capital_usd=1000, risk_pct=0.02, entry=100.0, sl=98.0, lev=5)
    assert qty > 0
    liq_long = liquidation_price("LONG", 100.0, 10)
    liq_short = liquidation_price("SHORT", 100.0, 10)
    assert liq_long < 100.0 and liq_short > 100.0
