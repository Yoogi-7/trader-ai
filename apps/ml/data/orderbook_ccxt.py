from __future__ import annotations
import os
import ccxt
from apps.ml.data.ccxt_client import _build_exchange, normalize_symbol

def fetch_orderbook_snapshot(symbol: str) -> dict:
    """
    Zwraca snapshot z top bid/ask oraz depth USD w +/-1% od mid.
    """
    ex = _build_exchange()
    mkt = normalize_symbol(symbol)
    ob = ex.fetch_order_book(mkt, limit=100)  # 100 poziomów, wystarczy do 1%
    bids = ob.get("bids", [])
    asks = ob.get("asks", [])
    ts = int(ob.get("timestamp") or ex.milliseconds())

    if not bids or not asks:
        raise RuntimeError("Orderbook empty")

    bid_px, bid_qty = float(bids[0][0]), float(bids[0][1])
    ask_px, ask_qty = float(asks[0][0]), float(asks[0][1])
    mid = (bid_px + ask_px) / 2.0
    spread_bps = (ask_px - bid_px) / mid * 10000.0

    # depth USD w ±1% mid
    lower = mid * 0.99
    upper = mid * 1.01
    depth_usd = 0.0
    for px, qty in bids:
        px = float(px); qty = float(qty)
        if px < lower: break
        depth_usd += px * qty
    for px, qty in asks:
        px = float(px); qty = float(qty)
        if px > upper: break
        depth_usd += px * qty

    return dict(
        symbol=symbol, ts=ts,
        bid_px=bid_px, bid_qty=bid_qty,
        ask_px=ask_px, ask_qty=ask_qty,
        mid_px=mid,
        spread_bps=spread_bps,
        depth_usd_1pct=depth_usd
    )
