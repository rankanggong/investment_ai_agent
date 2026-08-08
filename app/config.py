from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path
from typing import Any

from app.models.asset import Asset, Watchlist
from app.models.analysis import StrategyCondition, StrategyRuleDefinition


_STRATEGY_METRICS = {
    "drawdown_from_252d_high",
    "vix_level_percentile_252d",
    "credit_state",
    "credit_safety_state",
    "earnings_revision_negative",
}


@dataclass(frozen=True)
class TargetAllocationPolicy:
    basis: str = "supplied_invested_holding_cost"
    weights: dict[str, float] = field(default_factory=dict)
    tolerance: float | None = None


@dataclass(frozen=True)
class DailyBudgetPolicy:
    amount: float | None = None
    currency: str = "CNY"
    minimum_action_amount: float | None = None
    maximum_action_amount: float | None = None


@dataclass(frozen=True)
class ActionSizingPolicy:
    action: str
    method: str
    budget_fraction: float | None = None


@dataclass(frozen=True)
class RuleExecutionPermission:
    rule_id: str
    status: str
    valid_from: date | None = None
    valid_through: date | None = None
    maximum_amount: float | None = None


@dataclass(frozen=True)
class PortfolioFactorDefinition:
    factor_id: str
    symbols: tuple[str, ...]
    risk_components: tuple[str, ...] = ()
    risk_clusters: tuple[str, ...] = ()


@dataclass(frozen=True)
class FundamentalPolicy:
    valuation_stale_after_days: int | None = None
    earnings_revision_stale_after_days: int | None = None
    earnings_revision_materiality: float | None = None


@dataclass(frozen=True)
class NewsPolicy:
    entity_precision_threshold: float = 0.80
    max_age_days: int = 7


@dataclass(frozen=True)
class ReportProfile:
    base_currency: str = "CNY"
    target_allocations: dict[str, float] = field(default_factory=dict)
    daily_investment_budget: float | None = None
    usd_daily_spend: float | None = None
    gpt_questions: list[str] = field(default_factory=list)
    strategy_rules: tuple[StrategyRuleDefinition, ...] = ()
    target_allocation: TargetAllocationPolicy | None = None
    daily_budget: DailyBudgetPolicy | None = None
    action_sizing: tuple[ActionSizingPolicy, ...] = ()
    rule_execution_permissions: tuple[RuleExecutionPermission, ...] = ()
    portfolio_factors: tuple[PortfolioFactorDefinition, ...] = ()
    fundamental_policy: FundamentalPolicy = field(
        default_factory=FundamentalPolicy
    )
    news_policy: NewsPolicy = field(default_factory=NewsPolicy)

    def __post_init__(self) -> None:
        target = self.target_allocation or TargetAllocationPolicy(
            weights=dict(self.target_allocations)
        )
        budget = self.daily_budget or DailyBudgetPolicy(
            amount=self.daily_investment_budget,
            currency=self.base_currency,
        )
        if self.target_allocations and target.weights != self.target_allocations:
            raise ValueError("legacy and structured target allocations disagree")
        if (
            self.daily_investment_budget is not None
            and budget.amount != self.daily_investment_budget
        ):
            raise ValueError("legacy and structured daily budgets disagree")
        object.__setattr__(self, "target_allocation", target)
        object.__setattr__(self, "target_allocations", dict(target.weights))
        object.__setattr__(self, "daily_budget", budget)
        object.__setattr__(self, "daily_investment_budget", budget.amount)


def load_report_profile(path: Path | None) -> ReportProfile:
    if path is None or not path.exists():
        return ReportProfile()
    data = json.loads(path.read_text(encoding="utf-8"))
    target_policy = _load_target_allocation(data)
    budget_policy = _load_daily_budget(data)
    strategy_rules = _load_strategy_rules(data.get("strategy_rules", []))
    action_sizing = _load_action_sizing(data.get("action_sizing", []))
    permissions = _load_rule_execution_permissions(
        data.get("rule_execution_permissions", [])
    )
    rule_ids = {rule.rule_id for rule in strategy_rules}
    unknown_permissions = {
        permission.rule_id for permission in permissions
        if permission.rule_id not in rule_ids
    }
    if unknown_permissions:
        raise ValueError(
            "rule execution permissions reference unknown rules: "
            + ", ".join(sorted(unknown_permissions))
        )
    rule_actions = {rule.action for rule in strategy_rules}
    unknown_actions = {
        policy.action for policy in action_sizing
        if policy.action not in rule_actions
    }
    if unknown_actions:
        raise ValueError(
            "action sizing references unknown actions: "
            + ", ".join(sorted(unknown_actions))
        )
    return ReportProfile(
        base_currency=str(data.get("base_currency", "CNY")).upper(),
        usd_daily_spend=_optional_float(data.get("usd_daily_spend")),
        gpt_questions=[str(question) for question in data.get("gpt_questions", [])],
        strategy_rules=strategy_rules,
        target_allocation=target_policy,
        daily_budget=budget_policy,
        action_sizing=action_sizing,
        rule_execution_permissions=permissions,
        portfolio_factors=_load_portfolio_factors(
            data.get("portfolio_factors", [])
        ),
        fundamental_policy=_load_fundamental_policy(
            data.get("fundamental_policy", {})
        ),
        news_policy=_load_news_policy(data.get("news_policy", {})),
    )


def _load_target_allocation(data: dict[str, Any]) -> TargetAllocationPolicy:
    raw = data.get("target_allocation")
    if raw is None:
        raw = {"weights": data.get("target_allocations", {})}
    if not isinstance(raw, dict) or not isinstance(raw.get("weights", {}), dict):
        raise ValueError("target_allocation must contain a weights object")
    targets = {
        str(symbol).upper(): float(weight)
        for symbol, weight in raw.get("weights", {}).items()
    }
    if any(weight < 0 or weight > 1 for weight in targets.values()):
        raise ValueError("target allocation weights must be between 0 and 1")
    if targets and abs(sum(targets.values()) - 1.0) > 0.0001:
        raise ValueError("target allocation weights must sum to 1.0")
    tolerance = _optional_float(raw.get("tolerance"))
    if tolerance is not None and not 0 <= tolerance <= 1:
        raise ValueError("target allocation tolerance must be between 0 and 1")
    basis = str(raw.get("basis", "supplied_invested_holding_cost"))
    if basis != "supplied_invested_holding_cost":
        raise ValueError("unsupported target allocation basis")
    return TargetAllocationPolicy(basis, targets, tolerance)


def _load_daily_budget(data: dict[str, Any]) -> DailyBudgetPolicy:
    raw = data.get("daily_budget")
    if raw is None:
        raw = {"amount": data.get("daily_investment_budget")}
    if not isinstance(raw, dict):
        raise ValueError("daily_budget must be an object")
    amount = _optional_non_negative(raw.get("amount"), "daily budget amount")
    minimum = _optional_non_negative(
        raw.get("minimum_action_amount"), "minimum action amount"
    )
    maximum = _optional_non_negative(
        raw.get("maximum_action_amount"), "maximum action amount"
    )
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("minimum action amount cannot exceed maximum action amount")
    return DailyBudgetPolicy(
        amount=amount,
        currency=str(raw.get("currency", data.get("base_currency", "CNY"))).upper(),
        minimum_action_amount=minimum,
        maximum_action_amount=maximum,
    )


def _load_action_sizing(raw_items: Any) -> tuple[ActionSizingPolicy, ...]:
    if not isinstance(raw_items, list):
        raise ValueError("action_sizing must be a list")
    policies: list[ActionSizingPolicy] = []
    seen: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError("each action sizing policy must be an object")
        action = str(raw.get("action", "")).strip()
        method = str(raw.get("method", "")).strip()
        if not action or method not in {"daily_budget_fraction", "no_amount"}:
            raise ValueError(
                "action sizing requires an action and a supported method"
            )
        if action in seen:
            raise ValueError(f"duplicate action sizing policy: {action}")
        seen.add(action)
        fraction = _optional_float(raw.get("budget_fraction"))
        if method == "daily_budget_fraction" and (
            fraction is None or not 0 < fraction <= 1
        ):
            raise ValueError("action sizing budget_fraction must be above 0 and at most 1")
        if method == "no_amount" and fraction is not None:
            raise ValueError("no_amount action sizing cannot define budget_fraction")
        policies.append(ActionSizingPolicy(action, method, fraction))
    return tuple(policies)


def _load_rule_execution_permissions(
    raw_items: Any,
) -> tuple[RuleExecutionPermission, ...]:
    if not isinstance(raw_items, list):
        raise ValueError("rule_execution_permissions must be a list")
    permissions: list[RuleExecutionPermission] = []
    seen: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError("each rule execution permission must be an object")
        rule_id = str(raw.get("rule_id", "")).strip()
        status = str(raw.get("status", "denied")).strip()
        if not rule_id or status not in {"allowed", "denied"}:
            raise ValueError("rule execution permission requires rule_id and allowed/denied status")
        if rule_id in seen:
            raise ValueError(f"duplicate rule execution permission: {rule_id}")
        seen.add(rule_id)
        valid_from = _optional_date(raw.get("valid_from"))
        valid_through = _optional_date(raw.get("valid_through"))
        if valid_from and valid_through and valid_from > valid_through:
            raise ValueError("rule execution permission valid_from exceeds valid_through")
        permissions.append(
            RuleExecutionPermission(
                rule_id,
                status,
                valid_from,
                valid_through,
                _optional_non_negative(
                    raw.get("maximum_amount"), "permission maximum amount"
                ),
            )
        )
    return tuple(permissions)


def _load_portfolio_factors(
    raw_items: Any,
) -> tuple[PortfolioFactorDefinition, ...]:
    if not isinstance(raw_items, list):
        raise ValueError("portfolio_factors must be a list")
    allowed_components = {"breadth", "volatility"}
    allowed_clusters = {
        "broad_equity_growth", "sector_style", "mega_cap_companies",
        "rates_duration", "credit", "usd_cnh", "gold", "crypto",
    }
    definitions: list[PortfolioFactorDefinition] = []
    seen: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError("each portfolio factor must be an object")
        factor_id = str(raw.get("id", "")).strip()
        if any(
            not isinstance(raw.get(name, []), list)
            for name in ("symbols", "risk_components", "risk_clusters")
        ):
            raise ValueError("portfolio factor mappings must be lists")
        symbols = tuple(
            dict.fromkeys(str(item).upper() for item in raw.get("symbols", []))
        )
        components = tuple(
            dict.fromkeys(str(item) for item in raw.get("risk_components", []))
        )
        clusters = tuple(
            dict.fromkeys(str(item) for item in raw.get("risk_clusters", []))
        )
        if not factor_id or not symbols:
            raise ValueError("portfolio factor id and symbols are required")
        if factor_id in seen:
            raise ValueError(f"duplicate portfolio factor id: {factor_id}")
        if any(item not in allowed_components for item in components):
            raise ValueError(f"portfolio factor {factor_id} has an invalid risk component")
        if any(item not in allowed_clusters for item in clusters):
            raise ValueError(f"portfolio factor {factor_id} has an invalid risk cluster")
        seen.add(factor_id)
        definitions.append(
            PortfolioFactorDefinition(
                factor_id, symbols, components, clusters
            )
        )
    return tuple(definitions)


def _load_fundamental_policy(raw: Any) -> FundamentalPolicy:
    if not isinstance(raw, dict):
        raise ValueError("fundamental_policy must be an object")
    valuation_days = _optional_positive_int(
        raw.get("valuation_stale_after_days"),
        "valuation stale-after days",
    )
    revision_days = _optional_positive_int(
        raw.get("earnings_revision_stale_after_days"),
        "earnings revision stale-after days",
    )
    materiality = _optional_float(raw.get("earnings_revision_materiality"))
    if materiality is not None and not 0 <= materiality <= 1:
        raise ValueError("earnings revision materiality must be between 0 and 1")
    return FundamentalPolicy(valuation_days, revision_days, materiality)


def _load_news_policy(raw: Any) -> NewsPolicy:
    if not isinstance(raw, dict):
        raise ValueError("news_policy must be an object")
    threshold = float(raw.get("entity_precision_threshold", 0.80))
    if not 0 < threshold <= 1:
        raise ValueError("news entity precision threshold must be above 0 and at most 1")
    max_age_days = int(raw.get("max_age_days", 7))
    if max_age_days <= 0:
        raise ValueError("news max age days must be positive")
    return NewsPolicy(threshold, max_age_days)


def _load_strategy_rules(raw_rules: Any) -> tuple[StrategyRuleDefinition, ...]:
    if not isinstance(raw_rules, list):
        raise ValueError("strategy_rules must be a list")
    rules: list[StrategyRuleDefinition] = []
    seen_ids: set[str] = set()
    allowed_operators = {"==", "!=", ">", ">=", "<", "<="}
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            raise ValueError("each strategy rule must be an object")
        rule_id = str(raw_rule.get("id", "")).strip()
        symbol = str(raw_rule.get("symbol", "")).strip().upper()
        action = str(raw_rule.get("action", "")).strip()
        if not rule_id or not symbol or not action:
            raise ValueError("strategy rule id, symbol, and action are required")
        if rule_id in seen_ids:
            raise ValueError(f"duplicate strategy rule id: {rule_id}")
        seen_ids.add(rule_id)
        raw_conditions = raw_rule.get("conditions", [])
        if not isinstance(raw_conditions, list):
            raise ValueError(f"strategy rule {rule_id} conditions must be a list")
        conditions: list[StrategyCondition] = []
        for raw_condition in raw_conditions:
            if not isinstance(raw_condition, dict):
                raise ValueError(
                    f"strategy rule {rule_id} conditions must be objects"
                )
            metric = str(raw_condition.get("metric", "")).strip()
            operator = str(raw_condition.get("operator", "")).strip()
            if metric not in _STRATEGY_METRICS or operator not in allowed_operators:
                raise ValueError(
                    f"strategy rule {rule_id} has an invalid condition"
                )
            expected = raw_condition.get("value")
            if not isinstance(expected, (bool, int, float, str)):
                raise ValueError(
                    f"strategy rule {rule_id} condition value must be scalar"
                )
            conditions.append(
                StrategyCondition(metric, operator, expected)
            )
        rules.append(
            StrategyRuleDefinition(
                rule_id=rule_id,
                symbol=symbol,
                action=action,
                priority=int(raw_rule.get("priority", 0)),
                enabled=bool(raw_rule.get("enabled", True)),
                blocking=bool(raw_rule.get("blocking", False)),
                conditions=tuple(conditions),
            )
        )
    return tuple(rules)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_non_negative(value: Any, label: str) -> float | None:
    parsed = _optional_float(value)
    if parsed is not None and parsed < 0:
        raise ValueError(f"{label} must be non-negative")
    return parsed


def _optional_positive_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{label} must be positive")
    return parsed


def _optional_date(value: Any) -> date | None:
    if value in {None, ""}:
        return None
    return date.fromisoformat(str(value))


def load_watchlist(path: Path) -> Watchlist:
    data = _load_yaml_like(path)
    grouped_assets = data.get("assets", {})
    assets: list[Asset] = []

    for group, entries in grouped_assets.items():
        for entry in entries:
            if isinstance(entry, dict):
                symbol = str(entry["symbol"]).upper()
                assets.append(
                    Asset(
                        symbol=symbol,
                        name=entry.get("name"),
                        asset_type=entry.get("type"),
                        role=entry.get("role", group),
                        group=group,
                    )
                )
            else:
                symbol = str(entry).upper()
                assets.append(
                    Asset(
                        symbol=symbol,
                        name=symbol,
                        asset_type="etf",
                        role=_default_role_for_group(group),
                        group=group,
                    )
                )

    return Watchlist(assets=assets)


def _default_role_for_group(group: str) -> str:
    if group == "sectors":
        return "sector"
    return group


def _load_yaml_like(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_included_watchlist(path.read_text(encoding="utf-8"))

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in {path}")
    return loaded


def _parse_included_watchlist(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {"assets": {}}
    current_group: str | None = None
    current_item: dict[str, str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "assets:":
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent == 2 and stripped.endswith(":"):
            current_group = stripped[:-1]
            result["assets"][current_group] = []
            current_item = None
            continue

        if current_group is None:
            continue

        if stripped.startswith("- "):
            value = stripped[2:]
            if ":" in value:
                key, raw_value = value.split(":", 1)
                current_item = {key.strip(): raw_value.strip()}
                result["assets"][current_group].append(current_item)
            else:
                result["assets"][current_group].append(value.strip())
                current_item = None
            continue

        if current_item is not None and ":" in stripped:
            key, raw_value = stripped.split(":", 1)
            current_item[key.strip()] = raw_value.strip()

    return result
