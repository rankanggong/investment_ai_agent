from datetime import date

from app.analyzers.strategy_rule_engine import (
    StrategyExecutionContext,
    evaluate_strategy_decision,
)
from app.config import (
    ActionSizingPolicy,
    DailyBudgetPolicy,
    RuleExecutionPermission,
)
from app.models.analysis import (
    MacroContext,
    MarketBreadth,
    PriceSignal,
    StrategyCondition,
    StrategyRuleDefinition,
)


def signal(symbol: str, drawdown: float) -> PriceSignal:
    return PriceSignal(
        symbol=symbol,
        return_1d=0.0,
        return_5d=0.0,
        return_20d=0.0,
        volume_ratio_20d=None,
        volatility_zscore=None,
        is_unusual_move=False,
        reason="",
        latest=100.0,
        latest_date=date(2026, 7, 25),
        drawdown_from_high=drawdown,
    )


def breadth(vix_percentile: float | None = 0.9) -> MarketBreadth:
    return MarketBreadth(0, 0, 0, None, None, None, 20.0, vix_percentile)


def execution_context(
    *,
    permission_status: str = "allowed",
    investment_action_status: str = "available",
    factor_mapping_status: str = "available",
    maximum_permission_amount: float | None = None,
) -> StrategyExecutionContext:
    return StrategyExecutionContext(
        report_date=date(2026, 7, 25),
        daily_budget=DailyBudgetPolicy(1000, "CNY", 100, 400),
        action_sizing=(
            ActionSizingPolicy("base_investment", "daily_budget_fraction", 0.5),
        ),
        permissions=(
            RuleExecutionPermission(
                "base", permission_status,
                maximum_amount=maximum_permission_amount,
            ),
        ),
        available_investment_cash=1000,
        cash_currency="CNY",
        investment_action_status=investment_action_status,
        investment_action_reasons=(
            () if investment_action_status == "available"
            else ("target allocation missing",)
        ),
        factor_mapping_status=factor_mapping_status,
    )


def test_strategy_engine_selects_highest_priority_triggered_action():
    definitions = (
        StrategyRuleDefinition(
            "pause",
            "QQQ",
            "pause",
            100,
            True,
            True,
            (StrategyCondition("earnings_revision_negative", "==", True),),
        ),
        StrategyRuleDefinition(
            "level_2",
            "QQQ",
            "manual_add_level_2",
            30,
            True,
            False,
            (
                StrategyCondition("drawdown_from_252d_high", "<=", -0.12),
                StrategyCondition("vix_level_percentile_252d", ">", 0.8),
            ),
        ),
    )

    result = evaluate_strategy_decision(
        definitions,
        {"QQQ": signal("QQQ", -0.15)},
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        breadth(),
        fundamental_flags={"QQQ.earnings_revision_negative": False},
    )

    assert [rule.status for rule in result.rules] == ["waiting", "triggered"]
    assert result.action_readiness.status == "ready"
    assert result.action_readiness.candidate_action == "manual_add_level_2"
    assert result.action_readiness.rule_id == "level_2"
    assert result.action_readiness.human_approval_required is True


def test_strategy_engine_blocks_when_safety_rule_data_is_missing():
    definitions = (
        StrategyRuleDefinition(
            "pause",
            "QQQ",
            "pause",
            100,
            True,
            True,
            (StrategyCondition("earnings_revision_negative", "==", True),),
        ),
        StrategyRuleDefinition(
            "base",
            "QQQ",
            "base_investment",
            10,
            True,
            False,
        ),
    )

    result = evaluate_strategy_decision(
        definitions,
        {"QQQ": signal("QQQ", -0.02)},
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        breadth(),
    )

    assert result.rules[0].status == "blocked"
    assert result.rules[1].status == "triggered"
    assert result.action_readiness.status == "blocked"
    assert result.action_readiness.reasons == ("rule_blocked:pause",)


def test_strategy_engine_waits_when_conditions_are_not_met():
    definitions = (
        StrategyRuleDefinition(
            "level_1",
            "QQQ",
            "manual_add_level_1",
            20,
            True,
            False,
            (
                StrategyCondition("drawdown_from_252d_high", "<=", -0.08),
                StrategyCondition("credit_state", "!=", "credit_stress"),
            ),
        ),
    )

    result = evaluate_strategy_decision(
        definitions,
        {"QQQ": signal("QQQ", -0.02)},
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        breadth(),
    )

    assert result.rules[0].status == "waiting"
    assert result.action_readiness.status == "waiting_for_condition"


def test_execution_respects_investment_action_capability_gate():
    result = evaluate_strategy_decision(
        (
            StrategyRuleDefinition(
                "base", "QQQ", "base_investment", 10, True, False
            ),
        ),
        {"QQQ": signal("QQQ", -0.02)},
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        breadth(),
        execution_context=execution_context(investment_action_status="blocked"),
    )

    assert result.rules[0].status == "triggered"
    assert result.action_readiness.status == "ready"
    assert result.execution_readiness.status == "blocked"
    assert "target allocation missing" in result.execution_readiness.reasons


def test_execution_sizing_is_separate_from_triggered_rule_conditions():
    result = evaluate_strategy_decision(
        (
            StrategyRuleDefinition(
                "base", "QQQ", "base_investment", 10, True, False
            ),
        ),
        {"QQQ": signal("QQQ", -0.02)},
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        breadth(),
        execution_context=execution_context(),
    )

    assert result.action_readiness.status == "ready"
    assert result.execution_readiness.status == "awaiting_human_approval"
    assert result.execution_readiness.proposed_amount == 400
    assert "human_approval_required" in result.execution_readiness.reasons


def test_execution_sizing_blocks_without_policy_but_keeps_candidate():
    result = evaluate_strategy_decision(
        (
            StrategyRuleDefinition(
                "base", "QQQ", "base_investment", 10, True, False
            ),
        ),
        {"QQQ": signal("QQQ", -0.02)},
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        breadth(),
        execution_context=StrategyExecutionContext(
            date(2026, 7, 25),
            DailyBudgetPolicy(1000, "CNY"),
            (),
            (RuleExecutionPermission("base", "allowed"),),
            1000,
            "CNY",
            "available",
            (),
            "available",
        ),
    )

    assert result.action_readiness.candidate_action == "base_investment"
    assert result.execution_readiness.status == "blocked"
    assert "action_sizing_policy_not_configured" in result.execution_readiness.reasons


def test_execution_permission_is_default_deny_and_caps_allowed_amount():
    definition = (
        StrategyRuleDefinition(
            "base", "QQQ", "base_investment", 10, True, False
        ),
    )
    missing = evaluate_strategy_decision(
        definition,
        {"QQQ": signal("QQQ", -0.02)},
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        breadth(),
        execution_context=StrategyExecutionContext(
            date(2026, 7, 25),
            DailyBudgetPolicy(1000, "CNY"),
            (ActionSizingPolicy("base_investment", "daily_budget_fraction", 0.5),),
            (),
            1000,
            "CNY",
            "available",
            (),
            "available",
        ),
    )
    capped = evaluate_strategy_decision(
        definition,
        {"QQQ": signal("QQQ", -0.02)},
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        breadth(),
        execution_context=execution_context(maximum_permission_amount=250),
    )

    assert missing.action_readiness.status == "ready"
    assert "rule_execution_permission_not_configured" in missing.execution_readiness.reasons
    assert missing.execution_readiness.permission_status == "missing"
    assert capped.execution_readiness.proposed_amount == 250
    assert capped.execution_readiness.permission_status == "allowed"


def test_no_amount_safety_action_needs_permission_but_not_budget_or_targets():
    result = evaluate_strategy_decision(
        (StrategyRuleDefinition("pause", "QQQ", "pause", 100, True, True),),
        {"QQQ": signal("QQQ", -0.02)},
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        breadth(),
        execution_context=StrategyExecutionContext(
            date(2026, 7, 25),
            None,
            (ActionSizingPolicy("pause", "no_amount"),),
            (RuleExecutionPermission("pause", "allowed"),),
            None,
            None,
            "blocked",
            ("target allocations are not configured",),
            "blocked",
        ),
    )

    assert result.action_readiness.candidate_action == "pause"
    assert result.execution_readiness.status == "awaiting_human_approval"
    assert result.execution_readiness.proposed_amount is None
