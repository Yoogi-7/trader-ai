from apps.ml.trading.rules import expected_net_pct, Costs, should_publish

def test_expected_net_pct_maker_ok():
    c = Costs(maker_bps=2, taker_bps=10, slippage_bps=5, funding_perc_per_day=0.02)
    net = expected_net_pct(entry=100.0, tp=103.0, direction="LONG", costs=c, use_maker=True, hours_held=6)
    assert net > 2.0  # powinno przejść filtr

def test_should_publish_thresholds():
    ok, reason = should_publish(expected_net_pct_value=2.3, min_required=2.0, confidence=0.61, confidence_min=0.55)
    assert ok and reason is None
    ok, reason = should_publish(expected_net_pct_value=1.9, min_required=2.0, confidence=0.70, confidence_min=0.55)
    assert not ok and reason.startswith("net<")
    ok, reason = should_publish(expected_net_pct_value=3.0, min_required=2.0, confidence=0.40, confidence_min=0.55)
    assert not ok and reason.startswith("low_confidence")
