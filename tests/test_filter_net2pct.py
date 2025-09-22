
from apps.api.tools.filters import net_pct_after_costs, should_publish_signal

def test_net_pct_filter():
    net = net_pct_after_costs("LONG", entry=100, tp=103, sl=98, lev=5, fee_bps=7, slippage_bps=5, funding_bps=1)
    assert net > 2.0  # powinniśmy przejść próg 2%

def test_publish_gate():
    ok, reason = should_publish_signal(1.5, 2.0, confidence=0.6, conf_threshold=0.55)
    assert ok is False and "expected_net_pct<2.0%" in reason
    ok, reason = should_publish_signal(2.2, 2.0, confidence=0.4, conf_threshold=0.55)
    assert ok is False and "confidence<0.55" in reason
    ok, reason = should_publish_signal(2.2, 2.0, confidence=0.8, conf_threshold=0.55)
    assert ok is True
