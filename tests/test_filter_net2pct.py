
def expected_net_pct(entry, tp1, fee_bps=6, slippage_bps=5):
    gross = (tp1 - entry) / entry
    costs = (fee_bps + slippage_bps) / 10000.0
    return gross - costs

def test_filter_net2pct_pass():
    pct = expected_net_pct(100, 103)  # 3% gross - 0.11% costs = 2.89%
    assert pct >= 0.02

def test_filter_net2pct_block():
    pct = expected_net_pct(100, 101.5)  # 1.5% - 0.11% = 1.39% -> reject
    assert pct < 0.02
