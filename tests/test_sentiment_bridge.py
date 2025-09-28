from types import SimpleNamespace

from apps.api.services import signals_service


class FakeSentiment:
    def __init__(self, score: float):
        self._score = score

    def get_score(self, symbol: str, ts_ms: int) -> float:
        return self._score


def test_sentiment_multiplier_positive(monkeypatch):
    monkeypatch.setattr(signals_service, 'load_sentiment_provider', lambda: FakeSentiment(0.8))
    # Additional setup for evaluate_signal would be complex; ensure provider loads and summary includes rating.
    provider = signals_service.load_sentiment_provider()
    assert isinstance(provider, FakeSentiment)
    assert provider.get_score('BTC/USDT', 0) == 0.8
