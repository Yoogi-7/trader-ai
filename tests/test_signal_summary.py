from apps.api.services.signals_service import generate_ai_summary


def test_generate_ai_summary_contains_expected_keywords():
    summary = generate_ai_summary(
        symbol="BTCUSDT",
        tf_base="4h",
        direction="LONG",
        entry=60000.0,
        tp=[61200.0],
        sl=58800.0,
        expected_net_pct=0.03,
        confidence=0.72,
    )
    assert "LONG BTCUSDT" in summary
    assert "4H" in summary
    assert "TP" in summary and "SL" in summary
    assert "Net" in summary
    assert "0.72" in summary
