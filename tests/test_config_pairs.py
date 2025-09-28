import importlib

import apps.api.config as config_module


def _reload_with_pairs(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("PAIRS", raising=False)
    else:
        monkeypatch.setenv("PAIRS", value)
    return importlib.reload(config_module)


def test_settings_pairs_default(monkeypatch):
    module = _reload_with_pairs(monkeypatch, None)
    assert module.settings.pairs == [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "ADA/USDT",
        "SOL/USDT",
    ]


def test_settings_pairs_custom(monkeypatch):
    module = _reload_with_pairs(monkeypatch, "BTC/USDT , XRP/USDT ,")
    assert module.settings.pairs == ["BTC/USDT", "XRP/USDT"]
    # Restore defaults for other tests
    _reload_with_pairs(monkeypatch, None)
