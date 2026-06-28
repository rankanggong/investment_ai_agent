from app.analyzers.plan_impact_analyzer import analyze_plan_impact
from app.models.analysis import FundamentalEvent, MacroContext, NewsCluster, PriceSignal, SectorRotation


def signal(
    symbol: str,
    return_1d: float = 0.0,
    return_5d: float = 0.0,
    return_20d: float = 0.0,
    unusual: bool = False,
) -> PriceSignal:
    return PriceSignal(
        symbol=symbol,
        return_1d=return_1d,
        return_5d=return_5d,
        return_20d=return_20d,
        volume_ratio_20d=None,
        volatility_zscore=None,
        is_unusual_move=unusual,
        reason="large move" if unusual else "",
    )


def rotation(
    strong: list[str] | None = None,
    weak: list[str] | None = None,
) -> SectorRotation:
    return SectorRotation(
        strong_sectors=strong or [],
        weak_sectors=weak or [],
        risk_on_score=0.0,
        growth_vs_value="mixed",
        cyclical_vs_defensive="mixed",
        notes=[],
    )


def macro(regime: str = "mixed", rates: str = "mixed", gold: str = "mixed") -> MacroContext:
    return MacroContext(
        rates_context=rates,
        usd_context="mixed",
        credit_context="mixed",
        gold_context=gold,
        overall_regime=regime,
        notes=[],
    )


def test_plan_impact_identifies_accumulation_review_candidates():
    result = analyze_plan_impact(
        price_signals={
            "QQQ": signal("QQQ", return_5d=0.04, return_20d=0.08),
        },
        sector_rotation=rotation(),
        macro_context=macro("risk_on_with_macro_support"),
        news_clusters=[
            NewsCluster(
                topic="QQQ momentum",
                related_assets=["QQQ"],
                representative_headlines=["Nasdaq strength continues"],
                source_urls=["https://example.com/q"],
                item_count=2,
                confidence=0.8,
            )
        ],
        fundamental_events=[],
    )

    assert result.accumulation_review[0].symbol == "QQQ"
    assert result.accumulation_review[0].score == 4
    assert "20D trend positive" in result.accumulation_review[0].evidence
    assert "5D momentum positive" in result.accumulation_review[0].evidence
    assert "macro regime supports broad risk assets" in result.accumulation_review[0].evidence
    assert "important news cluster present" in result.accumulation_review[0].evidence
    assert result.derisk_review == []


def test_plan_impact_identifies_derisk_review_candidates():
    result = analyze_plan_impact(
        price_signals={
            "TLT": signal("TLT", return_1d=-0.05, return_5d=-0.04, return_20d=-0.07, unusual=True),
        },
        sector_rotation=rotation(),
        macro_context=macro(rates="rates_pressure"),
        news_clusters=[],
        fundamental_events=[],
    )

    assert result.derisk_review[0].symbol == "TLT"
    assert result.derisk_review[0].score == -4
    assert "20D trend negative" in result.derisk_review[0].evidence
    assert "5D momentum negative" in result.derisk_review[0].evidence
    assert "unusual negative price move" in result.derisk_review[0].evidence
    assert "rates pressure weighs on duration assets" in result.derisk_review[0].evidence
    assert result.accumulation_review == []


def test_plan_impact_stays_empty_when_evidence_is_weak():
    result = analyze_plan_impact(
        price_signals={
            "SPY": signal("SPY", return_5d=0.005, return_20d=0.01),
        },
        sector_rotation=rotation(),
        macro_context=macro(),
        news_clusters=[],
        fundamental_events=[],
    )

    assert result.accumulation_review == []
    assert result.derisk_review == []
    assert result.notes == ["No asset crossed accumulation or de-risk review thresholds."]


def test_plan_impact_treats_regulatory_events_as_derisk_evidence():
    result = analyze_plan_impact(
        price_signals={
            "AAPL": signal("AAPL", return_20d=-0.04),
        },
        sector_rotation=rotation(),
        macro_context=macro(),
        news_clusters=[],
        fundamental_events=[
            FundamentalEvent(
                event_type="regulatory_event",
                related_symbol="AAPL",
                headline="Apple faces regulator probe",
                publisher="Example",
                source_url="https://example.com/a",
                confidence=0.9,
            )
        ],
    )

    assert result.derisk_review[0].symbol == "AAPL"
    assert "regulatory event requires de-risk review" in result.derisk_review[0].evidence
