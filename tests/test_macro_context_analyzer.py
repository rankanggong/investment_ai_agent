from app.analyzers.macro_context_analyzer import analyze_macro_context
from app.models.analysis import PriceSignal


def signal(symbol, r5, r20):
    return PriceSignal(
        symbol=symbol,
        return_1d=0.0,
        return_5d=r5,
        return_20d=r20,
        volume_ratio_20d=None,
        volatility_zscore=None,
        is_unusual_move=False,
        reason="",
    )


def test_macro_context_identifies_supportive_risk_backdrop():
    result = analyze_macro_context(
        {
            "SPY": signal("SPY", 0.03, 0.05),
            "TLT": signal("TLT", 0.025, 0.04),
            "UUP": signal("UUP", -0.02, -0.03),
            "HYG": signal("HYG", 0.015, 0.02),
            "LQD": signal("LQD", 0.004, 0.01),
            "GLD": signal("GLD", 0.02, 0.03),
        }
    )

    assert result.rates_context == "duration_supported"
    assert result.usd_context == "usd_weakening"
    assert result.credit_context == "risk_appetite_supportive"
    assert result.gold_context == "gold_supported"
    assert result.overall_regime == "risk_on_with_macro_support"
    assert result.notes
