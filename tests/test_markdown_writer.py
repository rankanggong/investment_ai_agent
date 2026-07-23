from datetime import date
from decimal import Decimal

from app.models.analysis import (
    CompanyPriceBound,
    CompanyPriceBounds,
    DataCoverage,
    DataCoverageRow,
    DailySignalSummary,
    MacroContext,
    MacroEvidenceRow,
    NewsQualityGate,
    PriceSignal,
    SectorRotation,
)
from app.outputs.markdown_writer import render_daily_report
from app.steward.models import FxConversion, HoldingPosition, PortfolioReportState


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
    assert "Important News Clusters" not in content
    assert "Fundamental Events" not in content
    assert "What To Read Manually" not in content
    assert "stored news" not in content.lower()


def test_render_daily_report_includes_holdings_and_fx_but_not_cash():
    content = render_daily_report(
        report_date=date(2026, 7, 21),
        price_signals={},
        sector_rotation=SectorRotation(
            strong_sectors=[],
            weak_sectors=[],
            risk_on_score=0.0,
            growth_vs_value="mixed",
            cyclical_vs_defensive="mixed",
            notes=[],
        ),
        portfolio_state=PortfolioReportState(
            holdings=[
                HoldingPosition(
                    institution="broker",
                    account_label="fund",
                    symbol="QQQ",
                    name="NASDAQ ETF QDII",
                    quantity=Decimal("2977.30"),
                    currency="CNY",
                    unit_cost=Decimal("1.6928"),
                    as_of_date=date(2026, 7, 19),
                    acquired_on=date(2026, 7, 1),
                )
            ],
            fx_conversions=[
                FxConversion(
                    institution="bank",
                    account_label="usd",
                    fx_date=date(2026, 7, 15),
                    sold_currency="CNY",
                    sold_amount=Decimal("13587.60"),
                    bought_currency="USD",
                    bought_amount=Decimal("2000.00"),
                    fee_currency="CNY",
                    fee_amount=Decimal("0"),
                )
            ],
        ),
    )

    assert "## Portfolio Holdings" in content
    assert (
        "| broker | fund | QQQ | NASDAQ ETF QDII | CNY | 2977.30 | "
        "1.6928 | 5039.97 | 2026-07-19 |" in content
    )
    assert "## FX Conversions" in content
    assert (
        "| 2026-07-15 | bank / usd | CNY 13587.60 | USD 2000.00 | "
        "6.7938 CNY/USD | CNY 0.00 |" in content
    )
    assert "Cash Positions" not in content


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
            ],
            reason="No price, sector, or macro signal crossed review thresholds.",
        ),
    )

    assert content.index("## 0. What Matters Today") < content.index("## 1. Market Overview")
    assert "Status: no_material_signal" in content
    assert "- Price: no unusual moves" in content
    assert "Reason: No price, sector, or macro signal crossed review thresholds." in content


def test_render_daily_report_includes_data_coverage_after_daily_signal_summary():
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
        data_coverage=DataCoverage(
            rows=[
                DataCoverageRow(
                    category="Macro",
                    item="UUP",
                    status="missing",
                    rows=0,
                    latest="N/A",
                    detail="Needs at least 6 price rows for 5D macro context.",
                ),
            ],
            impacts=[
                "Section 4 may be unknown because UUP need at least 6 price rows.",
            ],
        ),
    )

    assert content.index("## 0. What Matters Today") < content.index("## Data Quality")
    assert content.index("## Data Quality") < content.index("## 1. Market Overview")
    assert "| Category | Item | Status | Rows | Latest | Detail |" in content
    assert (
        "| Macro | UUP | missing | 0 | N/A | "
        "Needs at least 6 price rows for 5D macro context. |"
    ) in content
    assert "Impact:" in content


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


def test_render_daily_report_fails_closed_without_action_labels():
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
        daily_signal_summary=DailySignalSummary(
            status="data_quality_failed",
            drivers=["News entity precision: 42.00% (threshold 80.00%)"],
            reason="Data quality failed: entity precision is below threshold.",
        ),
        news_quality=NewsQualityGate(
            entity_precision=0.42,
            precision_threshold=0.80,
            status="data_quality_review",
            news_score=None,
            fundamental_score=None,
            portfolio_action="unavailable",
            reasons=["Entity precision 42.00% is below threshold 80.00%."],
        ),
    )

    assert "Status: data_quality_failed" in content
    assert "Overall: data_quality_failed" in content
    assert "## 5. Triggered Strategy Rules" in content
    assert "- news_score: null" in content
    assert "- fundamental_score: null" in content
    assert "- portfolio_action: unavailable" in content
    assert "Portfolio action: unavailable" in content
    assert "High-conviction" not in content
    assert "de-risk" not in content.lower()


def test_render_daily_report_includes_detailed_macro_context():
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
    )

    assert "| Area | Signal | Evidence | Interpretation |" in content
    assert (
        "| Rates | rates_pressure | TLT 5D -2.10% | "
        "Long-duration proxies are weak, suggesting rate pressure. |"
    ) in content


def test_render_daily_report_includes_popular_company_price_bounds():
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
        company_price_bounds=CompanyPriceBounds(
            bounds=[
                CompanyPriceBound(
                    symbol="AAPL",
                    latest=210.0,
                    lower_review_bound=195.25,
                    upper_review_bound=230.75,
                    basis="60D range + volatility band",
                    confidence=0.85,
                    notes=[
                        "Recent range 195.25-225.10; volatility band 198.00-230.75."
                    ],
                )
            ],
            notes=["MSFT skipped: no price history available."],
        ),
    )

    assert "## 6. Popular Company Price Bounds" in content
    assert (
        "Research support only. These are price-derived review bands, not intrinsic value."
        in content
    )
    assert "| Company | Latest | Lower Review Bound | Upper Review Bound | Basis | Confidence |" in content
    assert "| AAPL | 210.00 | 195.25 | 230.75 | 60D range + volatility band | 0.85 |" in content
    assert "- AAPL: Recent range 195.25-225.10; volatility band 198.00-230.75." in content
    assert "- MSFT skipped: no price history available." in content


def test_render_daily_report_includes_report_signals_watch_next():
    from app.models.analysis import ReportSignals, SignalInsight, WatchNextItem

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
        report_signals=ReportSignals(
            insights=[
                SignalInsight(
                    subject="SOXX",
                    observed_fact="SOXX moved 2.80% in 1D.",
                    trigger_type="absolute_move",
                    evidence_type=["price_confirmed", "volume_confirmed"],
                    interpretation="Unusual price move detected.",
                    confidence="medium",
                    uncertainty="No confirmed fundamental event is linked to the move.",
                    watch_next="Whether SOXX confirms the move.",
                    invalidation="SOXX gives back the move.",
                )
            ],
            watch_next=[
                WatchNextItem(
                    subject="SOXX",
                    watch="Whether SOXX follow-through confirms the unusual move.",
                    confirmation="Move persists and volume remains above recent average.",
                    invalidation="SOXX gives back the move while volume normalizes.",
                    source="price",
                )
            ],
            manual_reading=[],
        ),
    )

    assert "Watch next:" in content
    assert "- SOXX: Whether SOXX follow-through confirms the unusual move." in content
    assert "What To Read Manually" not in content
