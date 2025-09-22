from dataclasses import dataclass

@dataclass
class Costs:
    maker_bps: float
    taker_bps: float
    slippage_bps: float
    funding_perc_per_day: float = 0.0  # uproszczenie; realnie wylicz po czasie trwania

def expected_net_pct(entry: float, tp: float, direction: str, costs: Costs, use_maker=True, hours_held=8.0) -> float:
    """
    Szacowany zysk netto w %, po kosztach (fee, slippage, funding).
    Prosty model: funding_proporcjonalny_do_czasu.
    """
    gross = ((tp - entry) / entry * (1 if direction == "LONG" else -1)) * 100.0
    fee_bps = costs.maker_bps if use_maker else costs.taker_bps
    fee_pct = fee_bps / 100.0
    slip_pct = costs.slippage_bps / 100.0
    funding_pct = costs.funding_perc_per_day * (hours_held / 24.0) * 100.0
    net = gross - fee_pct - slip_pct - funding_pct
    return net

def should_publish(expected_net_pct_value: float, min_required: float, confidence: float, confidence_min: float) -> tuple[bool, str | None]:
    if confidence < confidence_min:
        return False, f"low_confidence:{confidence:.2f}<{confidence_min:.2f}"
    if expected_net_pct_value < min_required:
        return False, f"net<{min_required:.2f}%"
    return True, None
