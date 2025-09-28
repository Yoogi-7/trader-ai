"""Cross-exchange arbitrage signal utilities."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import ccxt  # type: ignore


@dataclass
class MarketSnapshot:
    exchange: str
    symbol: str
    bid: float
    ask: float
    timestamp_ms: int


@dataclass
class ArbitrageOpportunity:
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread_pct: float
    timestamp_ms: int


def detect_arbitrage_opportunities(
    snapshots: Iterable[MarketSnapshot],
    *,
    min_spread_pct: float = 0.3,
) -> List[ArbitrageOpportunity]:
    """Detect arbitrage opportunities given market snapshots."""
    by_symbol: Dict[str, List[MarketSnapshot]] = {}
    for snap in snapshots:
        if snap.bid <= 0 or snap.ask <= 0:
            continue
        by_symbol.setdefault(snap.symbol, []).append(snap)

    opportunities: List[ArbitrageOpportunity] = []
    min_spread = max(0.0, float(min_spread_pct))

    for symbol, rows in by_symbol.items():
        if len(rows) < 2:
            continue
        best_buy = min(rows, key=lambda r: r.ask)
        best_sell = max(rows, key=lambda r: r.bid)
        if best_sell.bid <= best_buy.ask:
            continue
        spread_pct = (best_sell.bid - best_buy.ask) / best_buy.ask * 100.0
        if spread_pct < min_spread:
            continue
        ts = max(best_buy.timestamp_ms, best_sell.timestamp_ms)
        opportunities.append(
            ArbitrageOpportunity(
                symbol=symbol,
                buy_exchange=best_buy.exchange,
                sell_exchange=best_sell.exchange,
                buy_price=best_buy.ask,
                sell_price=best_sell.bid,
                spread_pct=spread_pct,
                timestamp_ms=ts,
            )
        )

    opportunities.sort(key=lambda o: o.spread_pct, reverse=True)
    return opportunities


class ExchangePriceFetcher:
    """Utility that fetches best bid/ask from multiple exchanges via ccxt."""

    def __init__(self, exchanges: List[str], market_type: str = "spot"):
        self._clients = {
            ex: getattr(ccxt, ex)({
                "enableRateLimit": True,
                "options": {"defaultType": market_type},
            })
            for ex in exchanges
        }

    def fetch_snapshot(self, exchange: str, symbol: str) -> Optional[MarketSnapshot]:
        client = self._clients.get(exchange)
        if client is None:
            return None
        try:
            book = client.fetch_order_book(symbol)
        except Exception:
            return None
        bids = book.get("bids") or []
        asks = book.get("asks") or []
        if not bids or not asks:
            return None
        bid_price = float(bids[0][0])
        ask_price = float(asks[0][0])
        if bid_price <= 0 or ask_price <= 0:
            return None
        ts = int(book.get("timestamp") or time.time() * 1000)
        return MarketSnapshot(exchange=exchange, symbol=symbol, bid=bid_price, ask=ask_price, timestamp_ms=ts)

    def scan(self, symbols: List[str], *, min_spread_pct: float = 0.3) -> List[ArbitrageOpportunity]:
        snapshots: List[MarketSnapshot] = []
        for ex in self._clients.keys():
            for sym in symbols:
                snap = self.fetch_snapshot(ex, sym)
                if snap:
                    snapshots.append(snap)
        return detect_arbitrage_opportunities(snapshots, min_spread_pct=min_spread_pct)
