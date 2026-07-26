from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.models.analysis import (
    ActionReadiness,
    ExecutionReadiness,
    MacroContext,
    MarketBreadth,
    PriceSignal,
    StrategyCondition,
    StrategyConditionResult,
    StrategyDecisionState,
    StrategyRuleDefinition,
    StrategyRuleResult,
)
from app.config import (
    ActionSizingPolicy,
    DailyBudgetPolicy,
    RuleExecutionPermission,
)


@dataclass(frozen=True)
class StrategyExecutionContext:
    report_date: date
    daily_budget: DailyBudgetPolicy | None
    action_sizing: tuple[ActionSizingPolicy, ...]
    permissions: tuple[RuleExecutionPermission, ...]
    available_investment_cash: float | None
    cash_currency: str | None
    investment_action_status: str = "blocked"
    investment_action_reasons: tuple[str, ...] = ()
    factor_mapping_status: str = "blocked"


def evaluate_strategy_decision(
    definitions: tuple[StrategyRuleDefinition, ...],
    price_signals: dict[str, PriceSignal],
    macro_context: MacroContext | None,
    market_breadth: MarketBreadth,
    fundamental_flags: dict[str, bool] | None = None,
    execution_context: StrategyExecutionContext | None = None,
) -> StrategyDecisionState:
    """Evaluate configured rules and derive one deterministic action state."""
    flags = fundamental_flags or {}
    results = tuple(
        _evaluate_rule(
            definition,
            price_signals,
            macro_context,
            market_breadth,
            flags,
        )
        for definition in definitions
    )
    readiness = _derive_action_readiness(results)
    execution = _derive_execution_readiness(
        readiness, execution_context
    )
    return StrategyDecisionState(results, readiness, execution)


def _derive_execution_readiness(
    readiness: ActionReadiness,
    context: StrategyExecutionContext | None,
) -> ExecutionReadiness:
    if readiness.status != "ready" or readiness.candidate_action is None:
        return ExecutionReadiness(
            "blocked", None, None, None,
            ("decision_candidate_not_ready", "human_approval_required"),
        )
    if context is None:
        return ExecutionReadiness(
            "blocked", None, None, None,
            ("execution_context_not_supplied", "human_approval_required"),
        )
    permission = next(
        (
            item for item in context.permissions
            if item.rule_id == readiness.rule_id
        ),
        None,
    )
    policy = next(
        (
            item for item in context.action_sizing
            if item.action == readiness.candidate_action
        ),
        None,
    )
    reasons: list[str] = []
    permission_reason = _permission_block_reason(permission, context.report_date)
    if permission_reason:
        reasons.append(permission_reason)
    if policy is None:
        reasons.append("action_sizing_policy_not_configured")
    if policy is not None and policy.method == "no_amount" and not reasons:
        return ExecutionReadiness(
            "awaiting_human_approval", None, None, policy.method,
            ("human_approval_required",),
            permission_status="allowed",
        )
    if context.investment_action_status != "available":
        reasons.extend(
            context.investment_action_reasons
            or ("investment_action_capability_not_available",)
        )
    if context.factor_mapping_status != "available":
        reasons.append("factor_mapping_not_complete")
    daily_budget = context.daily_budget
    if daily_budget is None or daily_budget.amount is None:
        reasons.append("daily_budget_not_configured")
    elif daily_budget.amount <= 0:
        reasons.append("daily_budget_not_positive")
    if context.available_investment_cash is None:
        reasons.append("investment_cash_unavailable")
    elif daily_budget is not None and context.cash_currency != daily_budget.currency:
        reasons.append("investment_cash_budget_currency_mismatch")
    if reasons:
        return ExecutionReadiness(
            "blocked", None,
            daily_budget.currency if daily_budget else None,
            policy.method if policy else None,
            tuple([*reasons, "human_approval_required"]),
            permission_status=(permission.status if permission else "missing"),
        )
    amount = daily_budget.amount * (policy.budget_fraction or 0)
    if daily_budget.maximum_action_amount is not None:
        amount = min(amount, daily_budget.maximum_action_amount)
    if permission and permission.maximum_amount is not None:
        amount = min(amount, permission.maximum_amount)
    amount = min(amount, context.available_investment_cash or 0)
    if (
        daily_budget.minimum_action_amount is not None
        and amount < daily_budget.minimum_action_amount
    ):
        return ExecutionReadiness(
            "blocked", amount, daily_budget.currency, policy.method,
            ("proposed_amount_below_minimum", "human_approval_required"),
            permission_status="allowed",
        )
    return ExecutionReadiness(
        "awaiting_human_approval",
        amount,
        daily_budget.currency,
        policy.method,
        ("human_approval_required",),
        permission_status="allowed",
    )


def _permission_block_reason(
    permission: RuleExecutionPermission | None,
    report_date: date,
) -> str:
    if permission is None:
        return "rule_execution_permission_not_configured"
    if permission.status != "allowed":
        return "rule_execution_permission_denied"
    if permission.valid_from and report_date < permission.valid_from:
        return "rule_execution_permission_not_yet_valid"
    if permission.valid_through and report_date > permission.valid_through:
        return "rule_execution_permission_expired"
    return ""


def _evaluate_rule(
    definition: StrategyRuleDefinition,
    price_signals: dict[str, PriceSignal],
    macro_context: MacroContext | None,
    market_breadth: MarketBreadth,
    fundamental_flags: dict[str, bool],
) -> StrategyRuleResult:
    if not definition.enabled:
        return StrategyRuleResult(
            name=definition.rule_id,
            status="disabled",
            observed="disabled",
            threshold="enabled must be true",
            reason="Rule is disabled by configuration.",
            rule_id=definition.rule_id,
            symbol=definition.symbol,
            action=definition.action,
            priority=definition.priority,
            blocking=definition.blocking,
        )

    condition_results = tuple(
        _evaluate_condition(
            condition,
            definition.symbol,
            price_signals,
            macro_context,
            market_breadth,
            fundamental_flags,
        )
        for condition in definition.conditions
    )
    if any(result.status == "blocked" for result in condition_results):
        status = "blocked"
    elif all(result.status == "passed" for result in condition_results):
        status = "triggered"
    else:
        status = "waiting"
    evidence_refs = tuple(
        dict.fromkeys(
            ref
            for condition_result in condition_results
            for ref in condition_result.evidence_refs
        )
    )
    return StrategyRuleResult(
        name=definition.rule_id,
        status=status,
        observed="; ".join(
            f"{result.metric}={_format_observed(result.observed)}"
            for result in condition_results
        ) or "No conditions; enabled rule is active.",
        threshold="; ".join(
            f"{condition.metric} {condition.operator} {condition.expected}"
            for condition in definition.conditions
        ) or "enabled = true",
        reason=_rule_reason(status, condition_results),
        evidence_refs=evidence_refs,
        rule_id=definition.rule_id,
        symbol=definition.symbol,
        action=definition.action,
        priority=definition.priority,
        blocking=definition.blocking,
        condition_results=condition_results,
    )


def _evaluate_condition(
    condition: StrategyCondition,
    symbol: str,
    price_signals: dict[str, PriceSignal],
    macro_context: MacroContext | None,
    market_breadth: MarketBreadth,
    fundamental_flags: dict[str, bool],
) -> StrategyConditionResult:
    observed, evidence_refs, missing_reason = _resolve_metric(
        condition.metric,
        symbol,
        price_signals,
        macro_context,
        market_breadth,
        fundamental_flags,
    )
    if missing_reason:
        return StrategyConditionResult(
            metric=condition.metric,
            operator=condition.operator,
            expected=condition.expected,
            observed=None,
            status="blocked",
            reason=missing_reason,
            evidence_refs=evidence_refs,
        )
    try:
        passed = _compare(observed, condition.operator, condition.expected)
    except (TypeError, ValueError):
        return StrategyConditionResult(
            metric=condition.metric,
            operator=condition.operator,
            expected=condition.expected,
            observed=observed,
            status="blocked",
            reason=f"incompatible_condition_types:{condition.metric}",
            evidence_refs=evidence_refs,
        )
    return StrategyConditionResult(
        metric=condition.metric,
        operator=condition.operator,
        expected=condition.expected,
        observed=observed,
        status="passed" if passed else "failed",
        reason="condition_passed" if passed else "condition_not_met",
        evidence_refs=evidence_refs,
    )


def _resolve_metric(
    metric: str,
    symbol: str,
    price_signals: dict[str, PriceSignal],
    macro_context: MacroContext | None,
    market_breadth: MarketBreadth,
    fundamental_flags: dict[str, bool],
) -> tuple[bool | float | str | None, tuple[str, ...], str]:
    if metric == "drawdown_from_252d_high":
        signal = price_signals.get(symbol)
        value = signal.drawdown_from_252d_high if signal else None
        ref = _price_ref(signal, symbol)
        return value, (ref,), "" if value is not None else f"missing_metric:{metric}"
    if metric == "vix_level_percentile_252d":
        value = market_breadth.vix_level_percentile_252d
        return (
            value,
            ("BREADTH:VIX",),
            "" if value is not None else f"missing_metric:{metric}",
        )
    if metric == "credit_state":
        value = macro_context.credit_context if macro_context else None
        if value == "unknown":
            value = None
        return (
            value,
            ("MACRO:CREDIT",),
            "" if value is not None else f"missing_metric:{metric}",
        )
    if metric == "earnings_revision_negative":
        key = f"{symbol}.earnings_revision_negative"
        value = fundamental_flags.get(key)
        if value is None:
            value = fundamental_flags.get("earnings_revision_negative")
        return (
            value,
            (f"FUNDAMENTAL:{symbol}:EARNINGS_REVISION",),
            "" if value is not None else f"missing_metric:{metric}",
        )
    return None, (), f"unsupported_metric:{metric}"


def _derive_action_readiness(
    results: tuple[StrategyRuleResult, ...],
) -> ActionReadiness:
    enabled = tuple(result for result in results if result.status != "disabled")
    if not enabled:
        return ActionReadiness(
            "blocked",
            None,
            None,
            None,
            ("strategy_rules_not_configured",),
        )

    blocked = tuple(result for result in enabled if result.status == "blocked")
    if blocked:
        return ActionReadiness(
            "blocked",
            None,
            None,
            None,
            tuple(f"rule_blocked:{result.rule_id}" for result in blocked),
            tuple(
                dict.fromkeys(
                    ref for result in blocked for ref in result.evidence_refs
                )
            ),
        )

    triggered = sorted(
        (result for result in enabled if result.status == "triggered"),
        key=lambda result: (result.blocking, result.priority),
        reverse=True,
    )
    if triggered:
        selected = triggered[0]
        return ActionReadiness(
            "ready",
            selected.action,
            selected.symbol,
            selected.rule_id,
            ("deterministic_rule_triggered", "human_approval_required"),
            selected.evidence_refs,
        )

    return ActionReadiness(
        "waiting_for_condition",
        None,
        None,
        None,
        ("no_strategy_condition_triggered",),
        tuple(
            dict.fromkeys(ref for result in enabled for ref in result.evidence_refs)
        ),
    )


def _compare(
    observed: bool | float | str | None,
    operator: str,
    expected: bool | float | str,
) -> bool:
    if observed is None:
        raise ValueError("observed value is missing")
    if operator == "==":
        return observed == expected
    if operator == "!=":
        return observed != expected
    if isinstance(observed, bool) or isinstance(expected, bool):
        raise TypeError("boolean values support only equality operators")
    if not isinstance(observed, (int, float)) or not isinstance(
        expected, (int, float)
    ):
        raise TypeError("ordered comparisons require numeric values")
    if operator == ">":
        return observed > expected
    if operator == ">=":
        return observed >= expected
    if operator == "<":
        return observed < expected
    if operator == "<=":
        return observed <= expected
    raise ValueError(f"unsupported operator: {operator}")


def _rule_reason(
    status: str,
    conditions: tuple[StrategyConditionResult, ...],
) -> str:
    if status == "triggered":
        return "All configured conditions passed."
    if status == "waiting":
        failed = [result.metric for result in conditions if result.status == "failed"]
        return "Conditions not met: " + ", ".join(failed) + "."
    blocked = [result.reason for result in conditions if result.status == "blocked"]
    return "Rule cannot be evaluated: " + ", ".join(blocked) + "."


def _price_ref(signal: PriceSignal | None, symbol: str) -> str:
    observed = (
        signal.latest_date.isoformat()
        if signal is not None and signal.latest_date is not None
        else "N/A"
    )
    return f"PRICE:{symbol}:{observed}"


def _format_observed(value: bool | float | str | None) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return "N/A" if value is None else str(value)
