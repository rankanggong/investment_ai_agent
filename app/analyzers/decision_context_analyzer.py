from __future__ import annotations

from dataclasses import asdict
from datetime import date
import json

from app.config import ReportProfile
from app.models.analysis import (
    DecisionContext,
    DecisionEvidenceState,
    DecisionHistoryRecord,
    PortfolioImpactAnalysis,
    PortfolioSummary,
    RiskAssessment,
    StrategyDecisionState,
)


def build_decision_context(
    report_date: date,
    market_risk: RiskAssessment,
    portfolio_impact: PortfolioImpactAnalysis,
    portfolio: PortfolioSummary,
    profile: ReportProfile,
    decision: StrategyDecisionState,
    previous: DecisionHistoryRecord | None = None,
    decision_evidence: DecisionEvidenceState | None = None,
) -> DecisionContext:
    """Combine market, portfolio, funding, and permission state for one decision."""
    readiness = decision.action_readiness
    execution = decision.execution_readiness
    impact = portfolio_impact.impact
    current_allocation = {
        item.symbol: (
            round(item.current_weight, 6)
            if item.current_weight is not None
            else None
        )
        for item in portfolio.allocations
    }
    allocation_gaps = {
        item.symbol: round(item.weight_gap, 6)
        for item in portfolio.allocations
        if item.weight_gap is not None
    }
    context_gaps = [
        *portfolio_impact.factors.reasons,
        *impact.reasons,
    ]
    reasons = [
        *context_gaps,
        *readiness.reasons,
        *execution.reasons,
        *(decision_evidence.reasons if decision_evidence else ()),
    ]
    if decision_evidence is not None and decision_evidence.status != "available":
        context_gaps.append(
            f"decision_evidence_{decision_evidence.status}"
        )
    if not profile.target_allocations:
        reasons.append("target_allocation_not_configured")
        context_gaps.append("target_allocation_not_configured")
    if profile.daily_budget is None or profile.daily_budget.amount is None:
        reasons.append("daily_budget_not_configured")
        context_gaps.append("daily_budget_not_configured")
    if portfolio.investment_cash is None:
        reasons.append("investment_cash_unavailable")
        context_gaps.append("investment_cash_unavailable")
    critical = (
        market_risk.level == "unknown"
        or portfolio_impact.factors.status == "blocked"
        or impact.status == "blocked"
    )
    status = (
        "blocked" if critical else ("degraded" if context_gaps else "available")
    )
    dominant = next(
        (
            item for item in impact.items
            if item.factor_id == impact.dominant_factor_id
        ),
        None,
    )
    evidence_refs = tuple(
        dict.fromkeys(
            [
                "PORTFOLIO:ALLOCATION",
                "PORTFOLIO:FACTOR_IMPACT",
                "STATE:ACTION_READINESS",
                "STATE:EXECUTION_READINESS",
                *readiness.evidence_refs,
                *(dominant.evidence_refs if dominant else ()),
                *(decision_evidence.evidence_refs if decision_evidence else ()),
            ]
        )
    )
    budget = profile.daily_budget
    return DecisionContext(
        report_date=report_date,
        status=status,
        market_risk_score=market_risk.score,
        market_risk_level=market_risk.level,
        portfolio_impact_status=impact.status,
        dominant_factor_id=impact.dominant_factor_id,
        dominant_impact_score=impact.dominant_impact_score,
        factor_impact_scores={
            item.factor_id: item.impact_score for item in impact.items
        },
        current_allocation=current_allocation,
        target_allocation=dict(profile.target_allocations),
        allocation_gaps=allocation_gaps,
        daily_budget_amount=budget.amount if budget else None,
        daily_budget_currency=budget.currency if budget else None,
        available_investment_cash=portfolio.investment_cash,
        candidate_action=readiness.candidate_action,
        candidate_symbol=readiness.symbol,
        candidate_rule_id=readiness.rule_id,
        action_readiness_status=readiness.status,
        veto_status=readiness.veto_status,
        execution_readiness_status=execution.status,
        permission_status=execution.permission_status,
        proposed_amount=execution.proposed_amount,
        proposed_currency=execution.currency,
        transition=_decision_transition(previous, decision, decision_evidence),
        previous_report_date=previous.report_date if previous else None,
        reasons=tuple(dict.fromkeys(reasons)),
        evidence_refs=evidence_refs,
        decision_evidence=decision_evidence,
    )


def _decision_transition(
    previous: DecisionHistoryRecord | None,
    current: StrategyDecisionState,
    evidence: DecisionEvidenceState | None = None,
) -> str:
    if previous is None:
        return "baseline"
    readiness = current.action_readiness
    execution = current.execution_readiness
    if (
        previous.candidate_action,
        previous.symbol,
        previous.rule_id,
    ) != (
        readiness.candidate_action,
        readiness.symbol,
        readiness.rule_id,
    ):
        return "candidate_changed"
    if previous.readiness_status != readiness.status:
        return "action_readiness_changed"
    if previous.execution_status != execution.status:
        return "execution_readiness_changed"
    if previous.permission_status != execution.permission_status:
        return "permission_changed"
    if previous.proposed_amount != execution.proposed_amount:
        return "proposed_amount_changed"
    previous_evidence = previous.context.get("decision_evidence")
    current_evidence = asdict(evidence) if evidence is not None else None
    if json.dumps(previous_evidence, sort_keys=True) != json.dumps(
        current_evidence, sort_keys=True
    ):
        return "decision_evidence_changed"
    return "no_change"
