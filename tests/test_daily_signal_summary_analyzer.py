from app.analyzers.daily_signal_summary_analyzer import analyze_daily_signal_summary
from app.models.analysis import FundamentalEvent, MacroContext, PriceSignal, SectorRotation


def signal(symbol: str, unusual: bool = False) -> PriceSignal:
    return PriceSignal(
        symbol=symbol,
        return_1d=0.0,
        return_5d=0.0,
        return_20d=0.0,
        volume_ratio_20d=None,
        volatility_zscore=None,
        is_unusual_move=unusual,
        reason="large move" if unusual else "",
    )


def rotation(score: float = 0.0) -> SectorRotation:
    return SectorRotation(
        strong_sectors=[],
        weak_sectors=[],
        risk_on_score=score,
        growth_vs_value="mixed",
        cyclical_vs_defensive="mixed",
        notes=[],
    )


def mixed_macro() -> MacroContext:
    return MacroContext(
        rates_context="mixed",
        usd_context="mixed",
        credit_context="mixed",
        gold_context="mixed",
        overall_regime="mixed",
        notes=[],
    )


def test_summary_reports_no_material_signal_when_inputs_are_quiet():
    result = analyze_daily_signal_summary(
        price_signals={"SPY": signal("SPY")},
        sector_rotation=rotation(),
        macro_context=mixed_macro(),
        news_clusters=[],
        fundamental_events=[],
    )

    assert result.status == "no_material_signal"
    assert "Price: no unusual moves" in result.drivers
    assert "Sector rotation: mixed" in result.drivers
    assert "Macro: mixed" in result.drivers
    assert "News: no important clusters" in result.drivers
    assert "Fundamental events: none detected" in result.drivers
    assert (
        result.reason
        == "No price, sector, macro, news, or fundamental event crossed review thresholds."
    )


def test_summary_requires_review_for_unusual_price_moves_and_events():
    result = analyze_daily_signal_summary(
        price_signals={"AAPL": signal("AAPL", unusual=True)},
        sector_rotation=rotation(),
        macro_context=mixed_macro(),
        news_clusters=[],
        fundamental_events=[
            FundamentalEvent(
                event_type="earnings_release",
                related_symbol="AAPL",
                headline="Apple reports earnings",
                publisher="Reuters",
                source_url="https://example.com/a",
                confidence=0.85,
            )
        ],
    )

    assert result.status == "review_required"
    assert "Price: 1 unusual move" in result.drivers
    assert "Fundamental events: 1 detected" in result.drivers
    assert result.reason == "Review required because price moves and fundamental events crossed thresholds."


def test_summary_monitors_when_context_is_not_quiet_but_no_review_signal():
    result = analyze_daily_signal_summary(
        price_signals={"SPY": signal("SPY")},
        sector_rotation=rotation(score=0.45),
        macro_context=MacroContext(
            rates_context="rates_pressure",
            usd_context="usd_strengthening",
            credit_context="credit_stress",
            gold_context="gold_pressure",
            overall_regime="risk_off_with_macro_pressure",
            notes=[],
        ),
        news_clusters=[],
        fundamental_events=[],
    )

    assert result.status == "monitor"
    assert "Sector rotation: risk-on score 0.45" in result.drivers
    assert "Macro: risk_off_with_macro_pressure" in result.drivers
    assert result.reason == "Monitor because sector rotation and macro context crossed thresholds."
