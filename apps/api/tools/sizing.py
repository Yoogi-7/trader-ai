
# Sizing i uproszczona estymacja likwidacji (dla kontraktów USDT-M)
# NOTE: uproszczona, konserwatywna formuła likwidacji – różne giełdy mają różne progi

def position_size(capital_usd: float, risk_pct: float, entry: float, sl: float, lev: int) -> float:
    risk_usd = capital_usd * risk_pct
    dist = max(1e-6, abs(entry - sl))
    qty = risk_usd / dist
    qty *= lev / entry  # kontrakty kwotowane w USDT (qty * entry = nominal / lev)
    return max(0.0, qty)

def liquidation_price(direction: str, entry: float, lev: int, maintenance_pct: float = 0.005) -> float:
    # Bardzo uproszczony model (ostrożny): likwidacja w odległości ok. (1/lev + mm) od entry
    shift = entry * (1.0/float(lev) + maintenance_pct)
    if direction == "LONG":
        return entry - shift
    return entry + shift
