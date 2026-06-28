from datetime import date

from app.models.analysis import (
    DailySignalSummary,
    FundamentalEvent,
    MacroContext,
    MacroEvidenceRow,
    NewsCluster,
    PlanImpact,
    PlanImpactItem,
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
    assert "| Event | Asset | Review Type | Confidence | Why It Matters | Headline | Source |" in content
    assert (
        "| earnings_release | AAPL | fundamental_review | 0.85 | "
        "This event may affect fundamental assumptions. | "
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


def test_render_daily_report_includes_plan_impact_review():
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
        plan_impact=PlanImpact(
            accumulation_review=[
                PlanImpactItem(
                    symbol="QQQ",
                    score=4,
                    evidence=[
                        "20D trend positive",
                        "macro regime supports broad risk assets",
                    ],
                )
            ],
            derisk_review=[
                PlanImpactItem(
                    symbol="TLT",
                    score=-3,
                    evidence=[
                        "20D trend negative",
                        "rates pressure weighs on duration assets",
                    ],
                )
            ],
            notes=[],
        ),
    )

    assert "## 7. Impact On My Plan" in content
    assert "Research support only. Not a buy/sell instruction." in content
    assert "### High-conviction accumulation review" in content
    assert "| QQQ | 4 | 20D trend positive; macro regime supports broad risk assets |" in content
    assert "### High-conviction de-risk review" in content
    assert "| TLT | -3 | 20D trend negative; rates pressure weighs on duration assets |" in content
    assert "Deferred to Phase 5." not in content


def test_render_daily_report_includes_detailed_sections_four_to_six():
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
            rates_context="rates_pressure",
            usd_context="usd_strengthening",
            credit_context="credit_stress",
            gold_context="gold_pressure",
            overall_regime="risk_off_with_macro_pressure",
            notes=["High-yield credit weakness points to risk appetite stress."],
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
                topic="fed pressure",
                related_assets=["SPY"],
                representative_headlines=["SPY slips as rates rise"],
                source_urls=["https://example.com/a"],
                item_count=3,
                confidence=0.9,
                source_count=2,
                why_it_matters=(
                    "3 stored headlines from 2 sources mention SPY, so this cluster may explain "
                    "asset-specific attention."
                ),
                manual_read_urls=["https://example.com/a"],
            )
        ],
        fundamental_events=[
            FundamentalEvent(
                event_type="regulatory_event",
                related_symbol="NVDA",
                headline="Nvidia faces antitrust probe from regulator",
                publisher="Reuters",
                source_url="https://example.com/n",
                confidence=0.85,
                review_type="regulatory_risk_review",
                why_it_matters="Regulatory events can create legal, financial, or operating constraints.",
            )
        ],
    )

    assert "| Area | Signal | Evidence | Interpretation |" in content
    assert (
        "| Rates | rates_pressure | TLT 5D -2.10% | "
        "Long-duration proxies are weak, suggesting rate pressure. |"
    ) in content
    assert "Why it matters: 3 stored headlines from 2 sources mention SPY" in content
    assert "Sources: 2" in content
    assert "Manual read:" in content
    assert "- https://example.com/a" in content
    assert "| Event | Asset | Review Type | Confidence | Why It Matters | Headline | Source |" in content
    assert (
        "| regulatory_event | NVDA | regulatory_risk_review | 0.85 | "
        "Regulatory events can create legal, financial, or operating constraints. | "
        "Nvidia faces antitrust probe from regulator | Reuters (https://example.com/n) |"
    ) in content
