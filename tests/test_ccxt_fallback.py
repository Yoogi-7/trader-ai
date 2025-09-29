from apps.ml.ccxt_client import CcxtClient


def test_ccxt_client_offline_generates_data():
    client = CcxtClient()
    client._offline = True  # force offline mode
    candles = client.fetch_ohlcv("BTC/USDT", "1m", None, None)
    assert candles, "Expected synthetic candles when offline"
    first = candles[0]
    assert len(first) == 6
    assert first[1] > 0


def test_ccxt_client_switches_to_synthetic(monkeypatch):
    client = CcxtClient()

    def _raise(*_args, **_kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(client, "_fetch_with_ccxt", _raise)
    candles = client.fetch_ohlcv("ETH/USDT", "15m", None, None)
    assert candles
    assert client._offline is True
