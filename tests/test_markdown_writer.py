from datetime import date
from decimal import Decimal

from app.models.analysis import (
    CompanyPriceBound,
    CompanyPriceBounds,
    DataCoverage,
    DataCoverageRow,
    DailySignalSummary,
    MarketEvidence,
    MacroContext,
    MacroEvidenceRow,
    NewsQualityGate,
    PortfolioAllocation,
    PortfolioSummary,
    PriceSignal,
    RiskAssessment,
    SectorRotation,
    StrategyRuleResult,
)
from app.outputs.markdown_writer import render_daily_report
from app.steward.models import (
    CashPosition,
    FxConversion,
    HoldingPosition,
    PortfolioReportState,
)


def sector_rotation() -> SectorRotation:
    return SectorRotation(
        strong_sectors=["XLK"],
        weak_sectors=["XLU"],
        risk_on_score=-0.40,
        growth_vs_value="growth_leading",
        cyclical_vs_defensive="defensive_leading",
        notes=[],
    )


def test_render_daily_report_uses_new_section_order_and_appendix():
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
                latest=600.0,
                latest_date=date(2026, 5, 16),
            )
        },
        sector_rotation=sector_rotation(),
        daily_signal_summary=DailySignalSummary(
            status="monitor",
            drivers=[],
            reason="Sector risk is elevated.",
        ),
        changes=["Risk score: 22 → 35."],
        gpt_questions=["What changed?"],
    )

    headings = [
        "# Daily Market State - 2026-05-16",
        "## 0. Executive State",
        "## 1. Data Quality",
        "## 2. Portfolio Summary",
        "## 3. Changes Since Previous Report",
        "## 4. Key Market Evidence",
        "## 5. Triggered Rules",
        "## 6. GPT Analysis Tasks",
        "## Appendix",
    ]
    positions = [content.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "Possible Driver" not in content
    assert "Detection Reason" in content
    assert "### C. Company Price Bounds" in content
    assert "## 6. Popular Company Price Bounds" not in content


def test_data_quality_only_lists_missing_or_blocked_modules():
    content = render_daily_report(
        report_date=date(2026, 5, 16),
        price_signals={},
        sector_rotation=sector_rotation(),
        data_coverage=DataCoverage(
            rows=[
                DataCoverageRow(
                    "Prices", "SPY", "available", 125, "2026-05-16", "Available."
                ),
                DataCoverageRow(
                    "Macro", "^TNX", "missing", 0, "N/A", "No history."
                ),
            ],
            impacts=["Macro evidence is incomplete."],
        ),
        news_quality=NewsQualityGate(
            entity_precision=None,
            precision_threshold=0.8,
            status="disabled",
            news_score=None,
            fundamental_score=None,
            portfolio_action="unavailable",
            reasons=["News collection is disabled."],
        ),
    )

    quality = content.split("## 2. Portfolio Summary", 1)[0]
    assert "| Macro | ^TNX | missing | N/A | No history. |" in quality
    assert "| Prices | SPY | available" not in quality
    assert "| News | entity pipeline | blocked" in quality


def test_portfolio_summary_and_account_details_are_separated():
    portfolio_state = PortfolioReportState(
        holdings=[
            HoldingPosition(
                institution="broker",
                account_label="fund",
                symbol="QQQ",
                name="NASDAQ ETF",
                quantity=Decimal("10"),
                currency="CNY",
                unit_cost=Decimal("100"),
                as_of_date=date(2026, 7, 19),
            )
        ],
        fx_conversions=[
            FxConversion(
                institution="bank",
                account_label="usd",
                fx_date=date(2026, 7, 15),
                sold_currency="CNY",
                sold_amount=Decimal("700"),
                bought_currency="USD",
                bought_amount=Decimal("100"),
            )
        ],
        cash_positions=[
            CashPosition(
                institution="bank",
                account_label="usd",
                currency="USD",
                balance=Decimal("9000"),
                as_of_date=date(2026, 7, 19),
                cash_role="investable",
            )
        ],
    )
    summary = PortfolioSummary(
        base_currency="CNY",
        total_holding_cost=1000.0,
        allocations=[
            PortfolioAllocation("QQQ", 1000.0, 1.0, 0.8, -0.2, -200.0)
        ],
        daily_investment_budget=500.0,
        usd_cash=9000.0,
        usd_daily_spend=50.0,
        usd_coverage_days=180.0,
    )

    content = render_daily_report(
        report_date=date(2026, 7, 21),
        price_signals={},
        sector_rotation=sector_rotation(),
        portfolio_state=portfolio_state,
        portfolio_summary=summary,
    )

    assert "| QQQ | CNY 1000.00 | 100.00% | 80.00% | -20.00% | CNY -200.00 |" in content
    assert "Daily investment budget: CNY 500.00" in content
    assert "USD coverage days: 180.0" in content
    assert "### B. Account Detail" in content
    assert "| bank | usd | USD | 9000 | investable | 2026-07-19 |" in content


def test_key_evidence_separates_structure_from_short_term_and_explains_risk():
    content = render_daily_report(
        report_date=date(2026, 7, 21),
        price_signals={},
        sector_rotation=sector_rotation(),
        key_evidence=[
            MarketEvidence(
                symbol="QQQ",
                latest=500.0,
                return_1d=0.01,
                return_5d=0.03,
                return_20d=-0.08,
                medium_term_trend="medium_term_downtrend",
                short_term_state="countertrend_rebound",
                detection_reason="5D rebound opposes 20D trend",
            )
        ],
        strategy_rules=[
            StrategyRuleResult(
                name="Medium-term/short-term divergence",
                status="triggered",
                observed="QQQ",
                threshold="5D opposes 20D",
                reason="Trend divergence detected.",
            )
        ],
        risk_assessment=RiskAssessment(
            score=45,
            level="elevated",
            explanations=["Data-quality penalty: 20 points."],
        ),
        gpt_questions=["What confirms the rebound?"],
    )

    assert "medium_term_downtrend" in content
    assert "| Medium-term/short-term divergence | triggered | QQQ |" in content
    assert "Market risk: 45/100 (elevated)" in content
    assert "- Data-quality penalty: 20 points." in content
    assert "1. What confirms the rebound?" in content


def test_company_bounds_and_real_macro_evidence_are_in_appendix():
    content = render_daily_report(
        report_date=date(2026, 5, 16),
        price_signals={},
        sector_rotation=sector_rotation(),
        macro_context=MacroContext(
            rates_context="rates_pressure",
            usd_context="usd_strengthening",
            credit_context="mixed",
            gold_context="mixed",
            overall_regime="mixed",
            notes=[],
            evidence_rows=[
                MacroEvidenceRow(
                    "Rates",
                    "rates_pressure",
                    "US 10Y yield 4.50; 5D 2.00%",
                    "Yields are rising.",
                )
            ],
        ),
        company_price_bounds=CompanyPriceBounds(
            bounds=[
                CompanyPriceBound(
                    "AAPL",
                    210.0,
                    195.25,
                    230.75,
                    "60D range + volatility band",
                    0.85,
                )
            ],
            notes=[],
        ),
        price_sources={"^TNX": "yfinance"},
    )

    appendix = content.split("## Appendix", 1)[1]
    assert "| Rates | rates_pressure | US 10Y yield 4.50; 5D 2.00% |" in appendix
    assert "| AAPL | 210.00 | 195.25 | 230.75 |" in appendix
    assert "- ^TNX: yfinance" in appendix
