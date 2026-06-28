from datetime import date

from app.models.analysis import (
    DailySignalSummary,
    FundamentalEvent,
    MacroContext,
    NewsCluster,
    PriceSignal,
    SectorRotation,
)
from app.outputs.markdown_writer import render_daily_report


def test_render_daily_report_includes_required_sections():
    content = render_daily_report(
        report_date=date(2026, 5, 16),
        price_signals={
            "SPY": PriceSignal(
                "SPY",
                0.01,
                0.02,
                0.03,
                1.2,
                0.5,
                False,
                "",
            )
        },
        sector_rotation=SectorRotation(
            strong_sectors=["XLK"],
            weak_sectors=["XLU"],
            risk_on_score=0.5,
            growth_vs_value="growth_leading",
            cyclical_vs_defensive="unknown",
            notes=[],
        ),
    )

    assert "# Daily Market Brief - 2026-05-16" in content
    assert "## 1. Market Overview" in content
    assert "## 3. Sector Rotation" in content
    assert "| SPY | 1.00% | 2.00% | 3.00% |" in content


def test_render_daily_report_includes_daily_signal_summary_before_market_overview():
    content = render_daily_report(
        report_date=date(2026, 5, 16),
        price_signals={},
        sector_rotation=SectorRotation(
            strong_sectors=[],
            weak_sectors=[],
            risk_on_score=0.0,
            growth_vs_value="mixed",
            cyclical_vs_defensive="mixed",
            notes=[],
        ),
        daily_signal_summary=DailySignalSummary(
            status="no_material_signal",
            drivers=[
                "Price: no unusual moves",
                "Sector rotation: mixed",
                "Macro: mixed",
                "News: no important clusters",
                "Fundamental events: none detected",
            ],
            reason="No price, sector, macro, news, or fundamental event crossed review thresholds.",
        ),
    )

    assert content.index("## 0. What Matters Today") < content.index("## 1. Market Overview")
    assert "Status: no_material_signal" in content
    assert "- Price: no unusual moves" in content
    assert "- Fundamental events: none detected" in content
    assert (
        "Reason: No price, sector, macro, news, or fundamental event crossed review thresholds."
        in content
    )


def test_render_daily_report_includes_macro_context_when_available():
    content = render_daily_report(
        report_date=date(2026, 5, 16),
        price_signals={},
        sector_rotation=SectorRotation(
            strong_sectors=[],
            weak_sectors=[],
            risk_on_score=0.0,
            growth_vs_value="unknown",
            cyclical_vs_defensive="unknown",
            notes=[],
        ),
        macro_context=MacroContext(
            rates_context="duration_supported",
            usd_context="usd_weakening",
            credit_context="risk_appetite_supportive",
            gold_context="gold_supported",
            overall_regime="risk_on_with_macro_support",
            notes=["Long-duration proxies are firm."],
        ),
    )

    assert "## 4. Macro Context" in content
    assert "Rates: duration_supported" in content
    assert "USD: usd_weakening" in content
    assert "Credit: risk_appetite_supportive" in content
    assert "Gold: gold_supported" in content
    assert "Regime: risk_on_with_macro_support" in content
    assert "- Long-duration proxies are firm." in content


def test_render_daily_report_includes_news_clusters_when_available():
    content = render_daily_report(
        report_date=date(2026, 5, 16),
        price_signals={},
        sector_rotation=SectorRotation(
            strong_sectors=[],
            weak_sectors=[],
            risk_on_score=0.0,
            growth_vs_value="unknown",
            cyclical_vs_defensive="unknown",
            notes=[],
        ),
        news_clusters=[
            NewsCluster(
                topic="fed hopes",
                related_assets=["SPY"],
                representative_headlines=["SPY rallies as Fed hopes lift market"],
                source_urls=["https://example.com/a"],
                item_count=2,
                confidence=0.8,
            )
        ],
    )

    assert "## 5. Important News Clusters" in content
    assert "### fed hopes" in content
    assert "Assets: SPY" in content
    assert "Items: 2" in content
    assert "Confidence: 0.80" in content
    assert "- SPY rallies as Fed hopes lift market (https://example.com/a)" in content


def test_render_daily_report_includes_fundamental_events_when_available():
    content = render_daily_report(
        report_date=date(2026, 5, 16),
        price_signals={},
        sector_rotation=SectorRotation(
            strong_sectors=[],
            weak_sectors=[],
            risk_on_score=0.0,
            growth_vs_value="unknown",
            cyclical_vs_defensive="unknown",
            notes=[],
        ),
        fundamental_events=[
            FundamentalEvent(
                event_type="earnings_release",
                related_symbol="AAPL",
                headline="Apple reports quarterly earnings and revenue beat estimates",
                publisher="Reuters",
                source_url="https://example.com/a",
                confidence=0.85,
            )
        ],
    )

    assert "## 6. Fundamental Events" in content
    assert "| Event | Asset | Confidence | Headline | Source |" in content
    assert (
        "| earnings_release | AAPL | 0.85 | "
        "Apple reports quarterly earnings and revenue beat estimates | "
        "Reuters (https://example.com/a) |"
    ) in content


def test_render_daily_report_shows_empty_fundamental_events_message():
    content = render_daily_report(
        report_date=date(2026, 5, 16),
        price_signals={},
        sector_rotation=SectorRotation(
            strong_sectors=[],
            weak_sectors=[],
            risk_on_score=0.0,
            growth_vs_value="unknown",
            cyclical_vs_defensive="unknown",
            notes=[],
        ),
        fundamental_events=[],
    )

    assert "No fundamental events detected from stored news." in content
