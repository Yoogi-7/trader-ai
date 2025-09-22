# PL: Filtr jakości sygnału — uwzględnia fee, slippage, funding i próg confid.
# EN: Signal quality filter — accounts for fees, slippage, funding and confidence.

def net_pct_after_costs(
    direction: str, entry: float, tp: float, sl: float, lev: float,
    fee_maker_bps: float, slippage_bps: float, funding_bps: float
) -> float:
    # zysk/strata procentowa względem entry (upraszczamy do liniowego RR)
    gross_pct = (tp - entry) / entry if direction == "LONG" else (entry - tp) / entry
    # koszty (podwójne fee + slippage + funding ~ pro-rata na life trade'u)
    fee_pct = (fee_maker_bps / 10000.0) * 2
    slip_pct = (slippage_bps / 10000.0)
    fund_pct = (funding_bps / 10000.0)
    net = (gross_pct - fee_pct - slip_pct - fund_pct) * float(lev)
    return net * 100.0  # w %

def should_publish_signal(expected_net_pct: float, min_required_pct: float, confidence: float | None, conf_threshold: float) -> (bool, str | None):
    if expected_net_pct < min_required_pct:
        return False, f"expected_net_pct<{min_required_pct}%"
    if confidence is not None and confidence < conf_threshold:
        return False, f"confidence<{conf_threshold}"
    return True, None
