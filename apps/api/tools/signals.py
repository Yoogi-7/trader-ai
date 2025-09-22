
from apps.api.tools.filters import net_pct_after_costs, should_publish_signal
from apps.api.config import get_settings

def publish_signal_decision(payload: dict):
    s = get_settings()
    entry = payload["entry"]
    sl = payload["sl"]
    tp1 = payload["tp"][0]
    lev = int(payload["leverage"])
    direction = payload["direction"]
    expected = net_pct_after_costs(direction, entry, tp1, sl, lev,
                                   fee_bps=s.MAKER_FEE_BPS, slippage_bps=s.SLIPPAGE_BPS, funding_bps=s.FUNDING_BPS)
    ok, reason = should_publish_signal(expected, s.MIN_NET_PCT, payload.get("confidence"), s.CONFIDENCE_THRESHOLD)
    return ok, expected, reason
