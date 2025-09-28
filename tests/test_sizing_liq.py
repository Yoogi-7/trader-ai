
def liquidation_price(entry: float, leverage: int, dir_long=True, maint_margin=0.005):
    if dir_long:
        return entry * (1 - (1/leverage) - maint_margin)
    else:
        return entry * (1 + (1/leverage) + maint_margin)

def test_liq_distance():
    entry = 100.0
    liq = liquidation_price(entry, leverage=10, dir_long=True)
    assert liq < entry * 0.9  # sufficiently far
