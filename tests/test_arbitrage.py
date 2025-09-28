from apps.ml.arbitrage import MarketSnapshot, detect_arbitrage_opportunities


def test_detect_arbitrage_basic():
    snaps = [
        MarketSnapshot(exchange='binance', symbol='BTC/USDT', bid=25050, ask=25040, timestamp_ms=1),
        MarketSnapshot(exchange='bybit', symbol='BTC/USDT', bid=25100, ask=25090, timestamp_ms=2),
        MarketSnapshot(exchange='kraken', symbol='BTC/USDT', bid=25020, ask=25010, timestamp_ms=1),
    ]
    opps = detect_arbitrage_opportunities(snaps, min_spread_pct=0.2)
    assert len(opps) == 1
    opp = opps[0]
    assert opp.buy_exchange == 'kraken'
    assert opp.sell_exchange == 'bybit'
    assert opp.symbol == 'BTC/USDT'
    assert opp.spread_pct > 0.2


def test_no_opportunity_when_spread_small():
    snaps = [
        MarketSnapshot(exchange='binance', symbol='ETH/USDT', bid=1700.1, ask=1700.0, timestamp_ms=1),
        MarketSnapshot(exchange='bybit', symbol='ETH/USDT', bid=1700.2, ask=1700.15, timestamp_ms=1),
    ]
    opps = detect_arbitrage_opportunities(snaps, min_spread_pct=0.5)
    assert opps == []
