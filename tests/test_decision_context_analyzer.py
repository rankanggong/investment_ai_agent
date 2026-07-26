from datetime import date

from app.analyzers.decision_context_analyzer import build_decision_context
from app.config import DailyBudgetPolicy, ReportProfile, TargetAllocationPolicy
from app.models.analysis import (
    ActionReadiness,
    DecisionHistoryRecord,
    DecisionEvidenceState,
    ExecutionReadiness,
    PortfolioAllocation,
    PortfolioFactorState,
    PortfolioImpactAnalysis,
    PortfolioImpactAssessment,
    PortfolioImpactItem,
    PortfolioSummary,
    RiskAssessment,
    StrategyDecisionState,
)


def test_decision_context_combines_personal_constraints_and_market_impact():
    context = build_decision_context(
        date(2026, 7, 26),
        RiskAssessment(24, "elevated", []),
        PortfolioImpactAnalysis(
            PortfolioFactorState("available", 1.0, ()),
            PortfolioImpactAssessment(
                "available",
                (
                    PortfolioImpactItem(
                        "growth_equity", 0.6, 20, 12, "watch", (),
                        ("PRICE:QQQ",),
                    ),
                ),
                dominant_factor_id="growth_equity",
                dominant_impact_score=12,
                level="watch",
            ),
        ),
        PortfolioSummary(
            "CNY",
            1000,
            [PortfolioAllocation("QQQ", 600, 0.6, 0.5, 0.1, 100)],
            200,
            0,
            None,
            None,
            investment_cash=500,
        ),
        ReportProfile(
            target_allocation=TargetAllocationPolicy(weights={"QQQ": 1.0}),
            daily_budget=DailyBudgetPolicy(200, "CNY"),
        ),
        StrategyDecisionState(
            (),
            ActionReadiness(
                "ready", "base_investment", "QQQ", "base", ("triggered",),
                ("PRICE:QQQ",),
            ),
            ExecutionReadiness(
                "awaiting_human_approval", 200, "CNY", "daily_budget_fraction",
                ("human_approval_required",), permission_status="allowed",
            ),
        ),
        decision_evidence=DecisionEvidenceState(
            "available", "available", "available", "available", ()
        ),
    )

    assert context.status == "available"
    assert context.transition == "baseline"
    assert context.dominant_factor_id == "growth_equity"
    assert context.factor_impact_scores == {"growth_equity": 12}
    assert context.current_allocation == {"QQQ": 0.6}
    assert context.target_allocation == {"QQQ": 1.0}
    assert context.allocation_gaps == {"QQQ": 0.1}
    assert context.daily_budget_amount == 200
    assert context.available_investment_cash == 500
    assert "PRICE:QQQ" in context.evidence_refs
    assert context.decision_evidence is not None
    assert context.decision_evidence.status == "available"


def test_decision_context_identifies_execution_transition():
    previous = DecisionHistoryRecord(
        date(2026, 7, 25), "ready", "base_investment", "QQQ", "base", {},
        execution_status="blocked", permission_status="allowed",
    )
    decision = StrategyDecisionState(
        (),
        ActionReadiness("ready", "base_investment", "QQQ", "base", ()),
        ExecutionReadiness(
            "awaiting_human_approval", 100, "CNY", "daily_budget_fraction",
            ("human_approval_required",), permission_status="allowed",
        ),
    )
    context = build_decision_context(
        date(2026, 7, 26),
        RiskAssessment(0, "low", []),
        PortfolioImpactAnalysis(
            PortfolioFactorState("available", 1.0, ()),
            PortfolioImpactAssessment("available", (), level="low"),
        ),
        PortfolioSummary(
            "CNY", 1000, [], 100, 0, None, None, investment_cash=1000
        ),
        ReportProfile(
            target_allocation=TargetAllocationPolicy(weights={"QQQ": 1.0}),
            daily_budget=DailyBudgetPolicy(100, "CNY"),
        ),
        decision,
        previous,
    )

    assert context.previous_report_date == date(2026, 7, 25)
    assert context.transition == "execution_readiness_changed"


def test_decision_context_journal_detects_p2_evidence_change():
    previous = DecisionHistoryRecord(
        date(2026, 7, 25),
        "waiting_for_condition",
        None,
        None,
        None,
        {},
        context={
            "decision_evidence": {
                "status": "blocked",
                "valuation_status": "blocked",
                "earnings_revision_status": "blocked",
                "news_entity_status": "disabled",
                "assets": [],
                "uncovered_symbols": [],
                "review_flags": [],
                "reasons": [],
                "evidence_refs": [],
            }
        },
    )
    decision = StrategyDecisionState(
        (),
        ActionReadiness(
            "waiting_for_condition", None, None, None,
            ("no_strategy_condition_triggered",),
        ),
    )
    context = build_decision_context(
        date(2026, 7, 26),
        RiskAssessment(0, "low", []),
        PortfolioImpactAnalysis(
            PortfolioFactorState("available", 1.0, ()),
            PortfolioImpactAssessment("available", (), level="low"),
        ),
        PortfolioSummary(
            "CNY", 1000, [], 100, 0, None, None, investment_cash=1000
        ),
        ReportProfile(
            target_allocation=TargetAllocationPolicy(weights={"QQQ": 1.0}),
            daily_budget=DailyBudgetPolicy(100, "CNY"),
        ),
        decision,
        previous,
        DecisionEvidenceState(
            "degraded", "available", "blocked", "disabled", ()
        ),
    )

    assert context.transition == "decision_evidence_changed"
