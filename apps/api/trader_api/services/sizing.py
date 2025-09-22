# Sizing: risk_$ = capital * risk_per_trade; qty = risk_$ / (|entry-sl|) * entry adj.

def calc_qty(capital: float, risk_perc: float, entry: float, sl: float, min_notional: float = 5.0):
    risk_dollar = capital * risk_perc
    distance = abs(entry - sl)
    if distance <= 0:
        return 0.0
    qty = (risk_dollar / distance)  # qty in quote/entry implied
    notional = qty * entry
    if notional < min_notional:
        # podbijamy do minimalnego notionalu
        qty = min_notional / entry
    return qty
