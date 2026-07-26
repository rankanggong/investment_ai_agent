from dataclasses import replace
from datetime import date
from decimal import Decimal

from app.analyzers.daily_report_state_analyzer import (
    analyze_fx_costs,
    analyze_fx_state,
    analyze_market_breadth,
    analyze_portfolio_summary,
    assess_market_risk,
    assess_portfolio_decision_risk,
    build_gpt_tasks,
    build_report_state,
    build_report_use_states,
    combine_data_quality,
    compare_report_states,
    extract_report_state,
    select_key_market_evidence,
    serialize_report_state,
)
from app.config import (
    DailyBudgetPolicy,
    ReportProfile,
    TargetAllocationPolicy,
)
from app.models.analysis import (
    DataCoverage,
    DataCoverageRow,
    DailySignalSummary,
    MacroContext,
    NewsQualityGate,
    PriceSignal,
)
from app.models.price import PriceBar
from app.steward.models import (
    CashPosition,
    FxConversion,
    HoldingPosition,
    PortfolioReportState,
)


def signal(
    symbol: str,
    *,
    latest: float = 100.0,
    r5: float = 0.0,
    r20: float = 0.0,
    unusual: bool = False,
    zscore: float = 0.0,
    atr: float = 0.0,
    percentile: float = 0.5,
    sma50: float | None = 95.0,
    sma200: float | None = 90.0,
) -> PriceSignal:
    return PriceSignal(
        symbol,
        0.01,
        r5,
        r20,
        1.0,
        zscore,
        unusual,
        "standardized trigger",
        latest=latest,
        latest_date=date(2026, 7, 24),
        sma_50=sma50,
        sma_200=sma200,
        drawdown_from_high=-0.05,
        atr_multiple=atr,
        return_zscore_60d=zscore,
        historical_percentile=percentile,
    )


def bar(day: date, close: float) -> PriceBar:
    return PriceBar(
        "USD/CNH", day, close, close, close, close, close, None, "test"
    )


def portfolio_state() -> PortfolioReportState:
    return PortfolioReportState(
        holdings=[
            HoldingPosition(
                "broker", "fund", "QQQ", "QQQ", Decimal("10"), "CNY",
                Decimal("100"), date(2026, 7, 24),
            )
        ],
        fx_conversions=[
            FxConversion(
                "bank", "usd", date(2026, 7, 15), "CNY", Decimal("700"),
                "USD", Decimal("100"), "CNY", Decimal("7"),
            )
        ],
        cash_positions=[
            CashPosition(
                "bank", "usd", "USD", Decimal("1200"), date(2026, 7, 24),
                cash_role="investment_cash",
            ),
            CashPosition(
                "bank", "reserve", "CNY", Decimal("5000"),
                date(2026, 7, 24), cash_role="reserved",
            ),
        ],
    )


def test_portfolio_summary_separates_cash_roles_and_invested_holdings():
    profile = ReportProfile(
        base_currency="CNY",
        target_allocations={"QQQ": 1.0},
        usd_daily_spend=10.0,
    )
    result = analyze_portfolio_summary(
        portfolio_state(),
        profile,
        {"USD/CNH": signal("USD/CNH", latest=7.0)},
        date(2026, 7, 25),
    )

    assert result.total_holding_cost == 1000.0
    assert result.allocations[0].current_weight == 1.0
    assert result.investment_cash == 8400.0
    assert result.reserved_cash == 5000.0
    assert result.usd_coverage_days == 120.0
    assert "invested holding cost" in result.notes[0]


def test_portfolio_freshness_is_layered_by_holdings_cash_and_fx_market():
    state = portfolio_state()
    result = analyze_portfolio_summary(
        PortfolioReportState(
            holdings=state.holdings,
            fx_conversions=state.fx_conversions,
            cash_positions=[
                CashPosition(
                    "bank", "usd", "USD", Decimal("1200"),
                    date(2026, 7, 1), cash_role="investment_cash",
                )
            ],
        ),
        ReportProfile(),
        {"USD/CNH": signal("USD/CNH", latest=7.0)},
        date(2026, 7, 25),
    )

    assert result.freshness is not None
    assert result.freshness.holdings.status == "available"
    assert result.freshness.cash.status == "stale"
    assert result.freshness.fx_market.status == "available"
    assert result.snapshot_status == "stale"


def test_market_risk_counts_correlated_assets_once_per_cluster():
    signals = {
        "AAPL": signal("AAPL", unusual=True, zscore=3.0),
        "MSFT": signal("MSFT", unusual=True, atr=2.0),
        "TLT": signal("TLT", unusual=True, percentile=0.99),
    }
    breadth = analyze_market_breadth(signals, {})
    result = assess_market_risk(signals, breadth)

    assert [item.cluster for item in result.clusters] == ["mega_cap_companies"]
    assert [item.symbol for item in result.single_asset_alerts] == ["TLT"]
    assert result.explanations[0].startswith(
        "Unusual-move risk: 1 single-asset alerts and 1 correlated clusters"
    )


def test_key_evidence_uses_medium_term_trend_and_standardized_metrics():
    result = select_key_market_evidence(
        {
            "QQQ": signal(
                "QQQ",
                latest=80,
                r5=0.03,
                unusual=True,
                zscore=2.5,
                atr=1.8,
                percentile=0.97,
                sma50=90,
                sma200=100,
            )
        }
    )[0]

    assert result.medium_term_trend == "medium_term_downtrend"
    assert result.short_term_state == "countertrend_rebound"
    assert result.return_zscore == 2.5
    assert result.evidence_ref == "PRICE:QQQ:2026-07-24"


def test_medium_term_trend_uses_close_against_both_moving_averages():
    result = select_key_market_evidence(
        {
            "QQQ": signal(
                "QQQ",
                latest=110,
                sma50=90,
                sma200=100,
            )
        }
    )[0]

    assert result.medium_term_trend == "medium_term_uptrend"


def test_combined_data_quality_prioritizes_news_blocked_and_portfolio_stale():
    state = portfolio_state()
    stale_state = PortfolioReportState(
        state.holdings,
        state.fx_conversions,
        [
            CashPosition(
                "bank", "usd", "USD", Decimal("100"), date(2026, 7, 1),
                cash_role="unknown",
            )
        ],
    )
    quality = combine_data_quality(
        DataCoverage([], [], status="available"),
        NewsQualityGate(
            None, 0.8, "disabled", None, None, "unavailable",
            ["News collection is disabled."],
        ),
        stale_state,
        date(2026, 7, 25),
    )

    assert quality.status == "degraded"
    statuses = {(row.category, row.item): row.status for row in quality.rows}
    assert statuses[("News", "entity pipeline")] == "blocked"
    assert statuses[("Portfolio", "cash and holdings")] == "stale"
    assert statuses[("Portfolio", "cash roles")] == "degraded"


def test_combined_data_quality_blocks_only_for_core_market_failure():
    quality = combine_data_quality(
        DataCoverage(
            [
                DataCoverageRow(
                    "Prices", "SPY", "missing", 0, "N/A", "No price history."
                )
            ],
            [],
        ),
        None,
        None,
        date(2026, 7, 25),
    )

    assert quality.status == "blocked"


def test_fx_cost_compares_all_in_rate_with_historical_usd_cnh():
    result = analyze_fx_costs(
        portfolio_state(),
        [
            bar(date(2026, 7, 14), 6.9),
            bar(date(2026, 7, 15), 7.0),
        ],
    )[0]

    assert result.effective_rate == 7.0
    assert result.all_in_rate == 7.07
    assert result.spot_rate == 7.0
    assert round(result.spot_premium or 0, 4) == 0.01
    assert "offshore approximation" in result.benchmark_note


def test_market_and_portfolio_state_round_trip_and_compare():
    summary = analyze_portfolio_summary(
        portfolio_state(),
        ReportProfile(),
        {"USD/CNH": signal("USD/CNH", latest=7.0)},
        date(2026, 7, 25),
    )
    breadth = analyze_market_breadth({}, {})
    market = assess_market_risk({}, breadth)
    portfolio = assess_portfolio_decision_risk(summary)
    fx_state = analyze_fx_state(
        portfolio_state(), summary, [bar(date(2026, 7, 25), 7.0)]
    )
    macro = MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", [])
    rotation = type(
        "Rotation",
        (),
        {
            "strong_sectors": [],
            "weak_sectors": [],
            "risk_on_score": 0.0,
        },
    )()
    use_states = build_report_use_states(
        market,
        macro,
        rotation,
        DataCoverage([], [], status="available"),
        summary,
        portfolio,
        NewsQualityGate(
            None, 0.8, "disabled", None, None, "unavailable", ["Disabled."]
        ),
        fx_state=fx_state,
    )
    state = build_report_state(
        use_states,
        market,
        portfolio,
        [],
        [],
        summary,
        fx_state,
    )
    restored = extract_report_state(serialize_report_state(state))

    assert state.capabilities["market_analysis"] == "available"
    assert state.invested_allocation == {"QQQ": 1.0}
    assert state.liquid_asset_allocation_status == "available"
    assert set(state.liquid_asset_allocation) == {"Cash", "QQQ"}
    assert state.fx_status == "degraded"
    changed = replace(
        state,
        portfolio_factor_exposures={"us_equity": 1.0},
        portfolio_impact_scores={"us_equity": 8},
        decision_context_status="available",
        decision_transition="execution_readiness_changed",
        dominant_portfolio_factor="us_equity",
        dominant_portfolio_impact_score=8,
        decision_context_reasons=("human_approval_required",),
        valuation_status="available",
        earnings_revision_status="available",
        earnings_revision_directions={"QQQ:FY2027:eps": "negative"},
    )
    changed_restored = extract_report_state(serialize_report_state(changed))
    assert changed_restored is not None
    assert changed_restored.portfolio_factor_exposures == {"us_equity": 1.0}
    assert changed_restored.portfolio_impact_scores == {"us_equity": 8}
    assert changed_restored.decision_context_status == "available"
    assert changed_restored.decision_transition == "execution_readiness_changed"
    assert changed_restored.dominant_portfolio_factor == "us_equity"
    assert changed_restored.valuation_status == "available"
    assert changed_restored.earnings_revision_directions == {
        "QQQ:FY2027:eps": "negative"
    }
    changes = compare_report_states(state, changed)
    assert any("Portfolio factor exposures" in item for item in changes)
    assert any("Portfolio impact scores" in item for item in changes)
    assert any("Decision context status" in item for item in changes)
    assert any("Decision transition" in item for item in changes)
    assert any("Valuation evidence status" in item for item in changes)
    assert any("Earnings revision directions" in item for item in changes)
    assert compare_report_states(restored, state) == ["No state changes detected."]


def test_extract_report_state_renames_legacy_structural_trend_values():
    content = (
        '<!-- report-state: {"executive_status":"review_required",'
        '"data_quality_status":"degraded","macro_regime":"mixed",'
        '"risk_score":20,"risk_level":"moderate","triggered_rules":[],'
        '"structural_trends":["SPY:structural_downtrend"],'
        '"portfolio_gaps":[]} -->'
    )

    restored = extract_report_state(content)

    assert restored is not None
    assert restored.medium_term_trends == ("SPY:legacy_downtrend",)


def test_gpt_tasks_include_evidence_refs_and_output_contract():
    evidence = select_key_market_evidence({"SPY": signal("SPY")})
    summary = analyze_portfolio_summary(
        portfolio_state(),
        ReportProfile(),
        {"USD/CNH": signal("USD/CNH", latest=7.0)},
        date(2026, 7, 25),
    )
    market = assess_market_risk({}, analyze_market_breadth({}, {}))
    portfolio = assess_portfolio_decision_risk(summary)
    use_states = build_report_use_states(
        market,
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        type(
            "Rotation",
            (),
            {"strong_sectors": [], "weak_sectors": [], "risk_on_score": 0.0},
        )(),
        DataCoverage([], [], status="available"),
        summary,
        portfolio,
        NewsQualityGate(
            None, 0.8, "disabled", None, None, "unavailable", ["Disabled."]
        ),
    )
    tasks = build_gpt_tasks(
        ReportProfile(gpt_questions=["What changed?"]),
        ["No state changes detected."],
        [],
        evidence,
        use_states,
    )

    assert tasks[0].evidence_refs == (
        "STATE:MARKET",
        "BREADTH:MARKET",
        "PRICE:SPY:2026-07-24",
    )
    assert "counterevidence" in tasks[0].expected_output
    assert "confidence" in tasks[0].confidence_requirement.lower()


def test_use_specific_states_do_not_block_market_for_stale_portfolio_or_news():
    state = portfolio_state()
    stale_state = PortfolioReportState(
        [
            HoldingPosition(
                "broker", "fund", "QQQ", "QQQ", Decimal("10"), "CNY",
                Decimal("100"), date(2026, 7, 1),
            )
        ],
        state.fx_conversions,
        [
            CashPosition(
                "bank", "cash", "CNY", Decimal("1000"), date(2026, 7, 1),
                cash_role="unknown",
            )
        ],
    )
    summary = analyze_portfolio_summary(
        stale_state,
        ReportProfile(),
        {},
        date(2026, 7, 25),
    )
    market = assess_market_risk(
        {"SPY": signal("SPY")},
        analyze_market_breadth({"SPY": signal("SPY")}, {}),
    )
    decision_risk = assess_portfolio_decision_risk(summary)
    states = build_report_use_states(
        market,
        MacroContext(
            "rates_pressure", "mixed", "mixed", "mixed", "mixed", []
        ),
        type(
            "Rotation",
            (),
            {
                "strong_sectors": ["XLE"],
                "weak_sectors": ["XLY"],
                "risk_on_score": 0.1,
            },
        )(),
        DataCoverage([], [], status="blocked"),
        summary,
        decision_risk,
        NewsQualityGate(
            None, 0.8, "disabled", None, None, "unavailable", ["Disabled."]
        ),
    )

    assert states.market.risk == "low"
    assert states.market.regime == "rotation_under_rate_pressure"
    assert states.market.actionability == "available"
    assert states.portfolio.risk == "unknown"
    assert states.portfolio.data_readiness == "blocked"
    assert states.portfolio.actionability == "blocked"
    assert states.news.quality == "blocked"
    assert states.news.actionability == "unavailable"
    assert states.data_quality is not None
    assert states.data_quality.overall.status == "blocked"
    assert states.data_quality.capabilities.market_analysis.status == "available"
    assert states.data_quality.capabilities.portfolio_analysis.status == "limited"
    assert states.data_quality.capabilities.news_analysis.status == "blocked"


def test_gpt_portfolio_task_is_blocked_and_uses_portfolio_refs():
    evidence = select_key_market_evidence({"SPY": signal("SPY")})
    summary = analyze_portfolio_summary(None, ReportProfile(), {})
    market = assess_market_risk({}, analyze_market_breadth({}, {}))
    decision_risk = assess_portfolio_decision_risk(summary)
    states = build_report_use_states(
        market,
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        type(
            "Rotation",
            (),
            {"strong_sectors": [], "weak_sectors": [], "risk_on_score": 0.0},
        )(),
        DataCoverage([], [], status="blocked"),
        summary,
        decision_risk,
        None,
    )

    task = build_gpt_tasks(
        ReportProfile(gpt_questions=["最大的目标仓位配置缺口是什么？"]),
        ["No state changes detected."],
        [],
        evidence,
        states,
    )[0]

    assert task.status == "blocked"
    assert task.task_id == "evaluate_allocation_gap"
    assert "STATE:PORTFOLIO" in task.evidence_refs
    assert "PORTFOLIO:ALLOCATION" in task.evidence_refs
    assert "do not infer a decision" in task.expected_output


def test_gpt_factor_impact_task_uses_portfolio_analysis_not_action_gate():
    summary = analyze_portfolio_summary(
        portfolio_state(),
        ReportProfile(),
        {"USD/CNH": signal("USD/CNH", latest=7.0)},
        date(2026, 7, 25),
    )
    market = assess_market_risk(
        {"SPY": signal("SPY")},
        analyze_market_breadth({"SPY": signal("SPY")}, {}),
    )
    states = build_report_use_states(
        market,
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        type(
            "Rotation",
            (),
            {"strong_sectors": [], "weak_sectors": [], "risk_on_score": 0.0},
        )(),
        DataCoverage([], [], status="available"),
        summary,
        assess_portfolio_decision_risk(summary),
        None,
        ReportProfile(),
    )

    task = build_gpt_tasks(
        ReportProfile(gpt_questions=["组合因子敞口如何映射为组合影响？"]),
        ["No state changes detected."],
        [],
        select_key_market_evidence({"SPY": signal("SPY")}),
        states,
    )[0]

    assert states.portfolio.actionability == "blocked"
    assert task.status == "ready"
    assert "PORTFOLIO:FACTOR_IMPACT" in task.evidence_refs


def test_portfolio_risk_separates_exposure_from_data_quality():
    summary = analyze_portfolio_summary(
        PortfolioReportState(
            holdings=[
                HoldingPosition(
                    "broker", "fund", "QQQ", "QQQ", Decimal("10"), "CNY",
                    Decimal("100"), date(2026, 7, 1),
                )
            ],
            fx_conversions=[],
            cash_positions=[
                CashPosition(
                    "bank", "cash", "CNY", Decimal("1000"),
                    date(2026, 7, 1), cash_role="unknown",
                )
            ],
        ),
        ReportProfile(target_allocations={"QQQ": 1.0}),
        {},
        date(2026, 7, 25),
    )

    risk = assess_portfolio_decision_risk(summary)

    assert risk.exposure_risk.score == 15
    assert risk.data_quality_risk.score == 45
    assert risk.decision_readiness == "blocked"


def test_gpt_fx_task_is_degraded_when_spot_comparison_is_missing():
    summary = analyze_portfolio_summary(
        portfolio_state(), ReportProfile(), {}, date(2026, 7, 25)
    )
    risk = assess_portfolio_decision_risk(summary)
    states = build_report_use_states(
        assess_market_risk({}, analyze_market_breadth({}, {})),
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        type(
            "Rotation",
            (),
            {"strong_sectors": [], "weak_sectors": [], "risk_on_score": 0.0},
        )(),
        DataCoverage([], [], status="degraded"),
        summary,
        risk,
        None,
        ReportProfile(),
        analyze_fx_state(portfolio_state(), summary, []),
    )

    task = build_gpt_tasks(
        ReportProfile(gpt_questions=["现在换汇成本是否合理？"]),
        ["No state changes detected."],
        [],
        [],
        states,
    )[0]

    assert task.status == "degraded"
    assert "usd_cnh_spot_unavailable" in task.blocked_reason


def test_portfolio_summary_exposes_invested_and_liquid_allocation_views():
    result = analyze_portfolio_summary(
        portfolio_state(),
        ReportProfile(target_allocations={"QQQ": 1.0}),
        {"USD/CNH": signal("USD/CNH", latest=7.0)},
        date(2026, 7, 25),
    )

    assert result.invested_allocation is not None
    assert result.invested_allocation.basis == "supplied_invested_holding_cost"
    assert result.invested_allocation.allocations[0].current_weight == 1.0
    assert result.liquid_asset_allocation is not None
    assert result.liquid_asset_allocation.status == "available"
    liquid_weights = {
        row.symbol: row.current_weight
        for row in result.liquid_asset_allocation.allocations
    }
    assert round(liquid_weights["QQQ"] or 0, 4) == 0.0694
    assert round(liquid_weights["Cash"] or 0, 4) == 0.9306


def test_investment_action_blocks_when_targets_do_not_cover_current_holdings():
    profile = ReportProfile(
        target_allocation=TargetAllocationPolicy(
            weights={"VOO": 1.0}, tolerance=0.03
        ),
        daily_budget=DailyBudgetPolicy(500, "CNY"),
    )
    summary = analyze_portfolio_summary(
        portfolio_state(),
        profile,
        {"USD/CNH": signal("USD/CNH", latest=7.0)},
        date(2026, 7, 25),
    )
    risk = assess_portfolio_decision_risk(summary)
    states = build_report_use_states(
        assess_market_risk(
            {"SPY": signal("SPY")},
            analyze_market_breadth({"SPY": signal("SPY")}, {}),
        ),
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        type(
            "Rotation",
            (),
            {"strong_sectors": [], "weak_sectors": [], "risk_on_score": 0.0},
        )(),
        DataCoverage([], [], status="available"),
        summary,
        risk,
        None,
        profile,
    )

    assert states.portfolio.actionability == "blocked"
    assert "QQQ" in states.portfolio.reason


def test_liquid_allocation_is_unavailable_for_unknown_cash_role():
    state = portfolio_state()
    summary = analyze_portfolio_summary(
        PortfolioReportState(
            state.holdings,
            state.fx_conversions,
            [
                CashPosition(
                    "bank", "cash", "CNY", Decimal("1000"),
                    date(2026, 7, 24), cash_role="unknown",
                )
            ],
        ),
        ReportProfile(),
        {},
        date(2026, 7, 25),
    )

    assert summary.liquid_asset_allocation is not None
    assert summary.liquid_asset_allocation.status == "unavailable"
    assert summary.liquid_asset_allocation.reason == "cash_role_not_configured"
    assert all(
        row.current_weight is None
        for row in summary.liquid_asset_allocation.allocations
    )


def test_fx_state_uses_current_spot_and_weighted_all_in_cost_basis():
    summary = analyze_portfolio_summary(
        portfolio_state(), ReportProfile(usd_daily_spend=10), {},
        date(2026, 7, 25),
    )

    state = analyze_fx_state(
        portfolio_state(),
        summary,
        [bar(date(2026, 7, 15), 7.0), bar(date(2026, 7, 25), 6.77)],
    )

    assert state.status == "available"
    assert state.spot_usd_cnh == 6.77
    assert state.cost_basis == 7.07
    assert round(state.difference_pct or 0, 4) == -0.0424
    assert state.coverage_days == 120.0


def test_fx_coverage_is_unavailable_without_daily_requirement():
    summary = analyze_portfolio_summary(
        portfolio_state(), ReportProfile(), {}, date(2026, 7, 25)
    )

    state = analyze_fx_state(
        portfolio_state(), summary, [bar(date(2026, 7, 25), 6.77)]
    )

    assert state.coverage_days is None
    assert state.coverage_status == "unavailable"
    assert state.status == "degraded"
    assert "usd_daily_spend_not_configured" in state.reasons
