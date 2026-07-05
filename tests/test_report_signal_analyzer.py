from datetime import datetime

from app.analyzers.report_signal_analyzer import analyze_report_signals
from app.models.analysis import (
    DataCoverage,
    DataCoverageRow,
    FundamentalEvent,
    MacroContext,
    MacroEvidenceRow,
    NewsCluster,
    PriceSignal,
    SectorRotation,
)


def price_signal(
    symbol: str,
    return_1d: float = 0.0,
    return_5d: float = 0.0,
    return_20d: float = 0.0,
    volume_ratio_20d: float | None = None,
    unusual: bool = False,
    reason: str = "",
) -> PriceSignal:
    return PriceSignal(
        symbol=symbol,
        return_1d=return_1d,
        return_5d=return_5d,
        return_20d=return_20d,
        volume_ratio_20d=volume_ratio_20d,
        volatility_zscore=None,
        is_unusual_move=unusual,
        reason=reason,
    )


def rotation() -> SectorRotation:
    return SectorRotation(
        strong_sectors=["SOXX"],
        weak_sectors=["XLE"],
        risk_on_score=0.42,
        growth_vs_value="growth_leading",
        cyclical_vs_defensive="mixed",
        notes=[],
    )


def test_report_signals_include_unusual_price_watch_item():
    result = analyze_report_signals(
        price_signals={
            "SOXX": price_signal(
                "SOXX",
                return_1d=0.028,
                return_5d=0.054,
                return_20d=0.092,
                volume_ratio_20d=2.3,
                unusual=True,
                reason="1D return exceeds recent volatility threshold; volume exceeds 2x recent average",
            )
        },
        sector_rotation=rotation(),
        macro_context=None,
        news_clusters=[],
        fundamental_events=[],
        data_coverage=None,
    )

    insight = next(item for item in result.insights if item.subject == "SOXX")
    assert insight.trigger_type == "absolute_move"
    assert insight.evidence_type == ["price_confirmed", "volume_confirmed"]
    assert insight.confidence == "medium"
    assert "SOXX moved 2.80% in 1D" in insight.observed_fact
    assert "No confirmed fundamental event is linked to the move." == insight.uncertainty

    watch = next(item for item in result.watch_next if item.subject == "SOXX")
    assert watch.source == "price"
    assert "volume" in watch.confirmation.lower()
    assert "gives back" in watch.invalidation


def test_report_signals_include_macro_news_fundamental_and_data_gap_items():
    result = analyze_report_signals(
        price_signals={"SPY": price_signal("SPY")},
        sector_rotation=rotation(),
        macro_context=MacroContext(
            rates_context="rates_pressure",
            usd_context="usd_strengthening",
            credit_context="credit_stress",
            gold_context="gold_pressure",
            overall_regime="risk_off_with_macro_pressure",
            notes=[],
            evidence_rows=[
                MacroEvidenceRow(
                    area="Rates",
                    signal="rates_pressure",
                    evidence="TLT 5D -2.10%",
                    interpretation="Long-duration proxies are weak, suggesting rate pressure.",
                )
            ],
        ),
        news_clusters=[
            NewsCluster(
                topic="ai chip demand",
                related_assets=["NVDA"],
                representative_headlines=["Nvidia rises on AI chip demand"],
                source_urls=["https://example.com/nvda"],
                item_count=2,
                confidence=0.8,
                source_count=1,
                why_it_matters="2 stored headlines mention NVDA.",
                manual_read_urls=["https://example.com/nvda"],
            )
        ],
        fundamental_events=[
            FundamentalEvent(
                event_type="earnings_release",
                related_symbol="AAPL",
                headline="Apple reports quarterly earnings",
                publisher="Reuters",
                source_url="https://example.com/aapl",
                confidence=0.85,
                review_type="earnings_review",
                why_it_matters="Earnings can reset assumptions.",
            )
        ],
        data_coverage=DataCoverage(
            rows=[
                DataCoverageRow(
                    category="Macro",
                    item="UUP",
                    status="missing",
                    rows=0,
                    latest="N/A",
                    detail="Needs at least 6 price rows for 5D macro context.",
                )
            ],
            impacts=["Section 4 may be unknown because UUP is missing."],
        ),
    )

    assert any(item.subject == "Rates" and item.trigger_type == "macro_proxy_shift" for item in result.insights)
    assert any(item.subject == "NVDA" and item.trigger_type == "news_cluster" for item in result.insights)
    assert any(item.subject == "AAPL" and item.trigger_type == "fundamental_event" for item in result.insights)
    assert any(item.subject == "Macro: UUP" and item.trigger_type == "data_gap" for item in result.insights)

    manual_urls = [item.url for item in result.manual_reading]
    assert manual_urls == ["https://example.com/aapl", "https://example.com/nvda"]
    assert result.manual_reading[0].priority == 100
    assert result.manual_reading[1].priority == 80


def test_report_signals_label_weak_sector_evidence_as_weakness():
    result = analyze_report_signals(
        price_signals={},
        sector_rotation=rotation(),
        macro_context=None,
        news_clusters=[],
        fundamental_events=[],
        data_coverage=None,
    )

    weak_insight = next(item for item in result.insights if item.subject == "XLE")
    assert weak_insight.trigger_type == "relative_weakness"
    assert weak_insight.evidence_type == ["relative_weakness_confirmed"]


def test_report_signals_keep_highest_priority_manual_read_for_shared_url():
    shared_url = "https://example.com/shared"

    result = analyze_report_signals(
        price_signals={},
        sector_rotation=SectorRotation(
            strong_sectors=[],
            weak_sectors=[],
            risk_on_score=0.0,
            growth_vs_value="mixed",
            cyclical_vs_defensive="mixed",
            notes=[],
        ),
        macro_context=None,
        news_clusters=[
            NewsCluster(
                topic="shared catalyst",
                related_assets=["NVDA"],
                representative_headlines=["Shared catalyst headline"],
                source_urls=[shared_url],
                item_count=1,
                confidence=0.7,
                source_count=1,
                why_it_matters="News item should lose to fundamental event priority.",
                manual_read_urls=[shared_url],
            )
        ],
        fundamental_events=[
            FundamentalEvent(
                event_type="earnings_release",
                related_symbol="NVDA",
                headline="Nvidia reports quarterly earnings",
                publisher="Reuters",
                source_url=shared_url,
                confidence=0.9,
                review_type="earnings_review",
                why_it_matters="Fundamental event should be retained for the shared URL.",
            )
        ],
        data_coverage=None,
    )

    assert len(result.manual_reading) == 1
    assert result.manual_reading[0].url == shared_url
    assert result.manual_reading[0].priority == 100
    assert result.manual_reading[0].source_type == "earnings_review"
    assert result.manual_reading[0].title == "Nvidia reports quarterly earnings"
