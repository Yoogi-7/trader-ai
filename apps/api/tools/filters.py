
# Filtry jakości sygnału: uwzględniają fee, slippage, funding i próg confidence.

def net_pct_after_costs(direction: str, entry: float, tp: float, sl: float, lev: int,
                        fee_bps: float, slippage_bps: float, funding_bps: float) -> float:
    gross = (tp - entry)/entry if direction == "LONG" else (entry - tp)/entry
    fees = (fee_bps/10000.0)*2
    slip = (slippage_bps/10000.0)
    funding = (funding_bps/10000.0)
    net = (gross - fees - slip - funding) * float(lev)
    return net * 100.0  # %

def should_publish_signal(expected_net_pct: float, min_required_pct: float, confidence: float | None, conf_threshold: float):
    if expected_net_pct < min_required_pct:
        return False, f"expected_net_pct<{min_required_pct}%"
    if confidence is not None and confidence < conf_threshold:
        return False, f"confidence<{conf_threshold}"
    return True, None
