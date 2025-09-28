# apps/ml/sentiment_plugin.py
# PL: Interfejs plug-in dla sentymentu. Domyślnie mock (0.0).
# EN: Sentiment plugin interface. Default mock returns 0.0.

from __future__ import annotations
import os
from typing import Protocol, Optional

class SentimentProvider(Protocol):
    def get_score(self, symbol: str, ts_ms: int) -> float:
        """Return sentiment score in [-1.0, 1.0] for given symbol/time."""
        ...

class MockSentiment(SentimentProvider):
    def get_score(self, symbol: str, ts_ms: int) -> float:
        return 0.0

def load_provider() -> SentimentProvider:
    """Dynamic loader from SENTIMENT_PROVIDER env (module:Class)."""
    spec = os.getenv("SENTIMENT_PROVIDER", "")
    if not spec:
        return MockSentiment()
    try:
        mod_name, cls_name = spec.split(":")
        mod = __import__(mod_name, fromlist=[cls_name])
        cls = getattr(mod, cls_name)
        return cls()  # type: ignore
    except Exception:
        # Fallback to mock if misconfigured
        return MockSentiment()
