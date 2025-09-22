from trader_api.services.filters import net_pct_after_costs, should_publish_signal

def test_net_filter_passes_when_over_2pct():
    pct = net_pct_after_costs("LONG", 100, 103, 98, 10, fee_maker_bps=7, slippage_bps=5, funding_bps=1)
    assert pct > 2.0

def test_should_publish_signal_confidence_threshold():
    ok, reason = should_publish_signal(2.5, 2.0, confidence=0.6, conf_threshold=0.58)
    assert ok and reason is None
    ok2, reason2 = should_publish_signal(2.5, 2.0, confidence=0.55, conf_threshold=0.58)
    assert not ok2 and "confidence" in reason2
