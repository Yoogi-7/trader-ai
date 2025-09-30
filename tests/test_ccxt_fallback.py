import pytest

from apps.ml.ccxt_client import CcxtClient


def test_ccxt_client_requires_initialised_exchange():
    client = CcxtClient()
    client.ex = None
    with pytest.raises(RuntimeError):
        client.fetch_ohlcv("BTC/USDT", "1m", None, None)


def test_ccxt_client_propagates_fetch_failures(monkeypatch):
    client = CcxtClient()

    def _raise(*_args, **_kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(client, "_fetch_with_ccxt", _raise)
    with pytest.raises(RuntimeError):
        client.fetch_ohlcv("ETH/USDT", "15m", None, None)


def test_ccxt_client_returns_empty_when_no_rows(monkeypatch):
    client = CcxtClient()

    def _empty(*_args, **_kwargs):
        return []

    monkeypatch.setattr(client, "_fetch_with_ccxt", _empty)
    out = client.fetch_ohlcv("ETH/USDT", "15m", None, None)
    assert out == []
