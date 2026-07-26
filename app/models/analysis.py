from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal


@dataclass(frozen=True)
class PriceSignal:
    symbol: str
    return_1d: float | None
    return_5d: float | None
    return_20d: float | None
    volume_ratio_20d: float | None
    volatility_zscore: float | None
    is_unusual_move: bool
    reason: str
    latest: float | None = None
    latest_date: date | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    distance_to_50d: float | None = None
    distance_to_200d: float | None = None
    drawdown_from_high: float | None = None
    atr_20: float | None = None
    atr_multiple: float | None = None
    return_zscore_60d: float | None = None
    historical_percentile: float | None = None
    sma_50_slope_20d: float | None = None

    @property
    def absolute_move_z_score_60d(self) -> float | None:
        return self.return_zscore_60d

    @property
    def absolute_move_percentile_252d(self) -> float | None:
        return self.historical_percentile

    @property
    def drawdown_from_252d_high(self) -> float | None:
        return self.drawdown_from_high


@dataclass(frozen=True)
class SectorRotation:
    strong_sectors: list[str]
    weak_sectors: list[str]
    risk_on_score: float
    growth_vs_value: str
    cyclical_vs_defensive: str
    notes: list[str]


@dataclass(frozen=True)
class DailySignalSummary:
    status: str
    drivers: list[str]
    reason: str


@dataclass(frozen=True)
class PlanImpactItem:
    symbol: str
    score: int
    evidence: list[str]


@dataclass(frozen=True)
class PlanImpact:
    accumulation_review: list[PlanImpactItem]
    derisk_review: list[PlanImpactItem]
    notes: list[str]


@dataclass(frozen=True)
class CompanyPriceBound:
    symbol: str
    latest: float
    lower_review_bound: float
    upper_review_bound: float
    basis: str
    confidence: float
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompanyPriceBounds:
    bounds: list[CompanyPriceBound]
    notes: list[str]


@dataclass(frozen=True)
class DataCoverageRow:
    category: str
    item: str
    status: str
    rows: int
    latest: str
    detail: str


@dataclass(frozen=True)
class DataCoverage:
    rows: list[DataCoverageRow]
    impacts: list[str]
    status: str = ""

    def __post_init__(self) -> None:
        if self.status:
            return
        computed = (
            "degraded"
            if any(row.status != "available" for row in self.rows)
            else "available"
        )
        object.__setattr__(self, "status", computed)


@dataclass(frozen=True)
class SignalInsight:
    subject: str
    observed_fact: str
    trigger_type: str
    evidence_type: list[str]
    interpretation: str
    confidence: str
    data_coverage: str = "available"
    uncertainty: str = ""
    watch_next: str = ""
    invalidation: str = ""


@dataclass(frozen=True)
class WatchNextItem:
    subject: str
    watch: str
    confirmation: str
    invalidation: str
    source: str


@dataclass(frozen=True)
class ManualReadItem:
    title: str
    url: str
    reason: str
    source_type: str
    related_symbol: str
    priority: int


@dataclass(frozen=True)
class ReportSignals:
    insights: list[SignalInsight]
    watch_next: list[WatchNextItem]
    manual_reading: list[ManualReadItem]


@dataclass(frozen=True)
class MacroEvidenceRow:
    area: str
    signal: str
    evidence: str
    interpretation: str


@dataclass(frozen=True)
class MacroContext:
    rates_context: str
    usd_context: str
    credit_context: str
    gold_context: str
    overall_regime: str
    notes: list[str]
    evidence_rows: list[MacroEvidenceRow] = field(default_factory=list)


@dataclass(frozen=True)
class PortfolioAllocation:
    symbol: str
    current_value: float | None
    current_weight: float | None
    target_weight: float | None
    weight_gap: float | None
    target_value_gap: float | None


@dataclass(frozen=True)
class PortfolioAllocationView:
    status: str
    basis: str
    total_value: float | None
    allocations: list[PortfolioAllocation]
    reason: str = ""


@dataclass(frozen=True)
class FreshnessLayer:
    status: str
    latest_date: date | None
    oldest_date: date | None
    maximum_age_days: int | None
    stale_after_days: int
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortfolioFreshness:
    holdings: FreshnessLayer
    cash: FreshnessLayer
    fx_market: FreshnessLayer


@dataclass(frozen=True)
class PortfolioSummary:
    base_currency: str
    total_holding_cost: float | None
    allocations: list[PortfolioAllocation]
    daily_investment_budget: float | None
    usd_cash: float
    usd_daily_spend: float | None
    usd_coverage_days: float | None
    investment_cash: float | None = None
    investment_source_cash: float | None = None
    reserved_cash: float | None = None
    emergency_cash: float | None = None
    unknown_cash: float | None = None
    snapshot_status: str = "unavailable"
    notes: list[str] = field(default_factory=list)
    invested_allocation: PortfolioAllocationView | None = None
    liquid_asset_allocation: PortfolioAllocationView | None = None
    freshness: PortfolioFreshness | None = None
    allocation_tolerance: float | None = None
    daily_budget_currency: str | None = None

    @property
    def investable_cash(self) -> float | None:
        """Compatibility name for the canonical investment_cash role."""
        return self.investment_cash

    @property
    def unclassified_cash(self) -> float | None:
        """Compatibility name for the canonical unknown role."""
        return self.unknown_cash


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    level: str
    explanations: list[str]
    scope: str = "market"
    clusters: list["RiskClusterAssessment"] = field(default_factory=list)
    single_asset_alerts: list["RiskAssetAlert"] = field(default_factory=list)
    components: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioFactorExposure:
    factor_id: str
    status: str
    weight: float | None
    symbols: tuple[str, ...]
    basis: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortfolioFactorState:
    status: str
    mapped_weight: float | None
    exposures: tuple[PortfolioFactorExposure, ...]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortfolioImpactItem:
    factor_id: str
    exposure_weight: float
    market_risk_points: int
    impact_score: int
    level: str
    drivers: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortfolioImpactAssessment:
    status: str
    items: tuple[PortfolioImpactItem, ...]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortfolioImpactAnalysis:
    factors: PortfolioFactorState
    impact: PortfolioImpactAssessment


@dataclass(frozen=True)
class RiskClusterAssessment:
    cluster: str
    symbols: tuple[str, ...]
    severity: float
    points: int
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class RiskAssetAlert:
    symbol: str
    category: str
    severity: float
    points: int
    evidence_ref: str


@dataclass(frozen=True)
class PortfolioRiskAssessment:
    exposure_risk: RiskAssessment
    data_quality_risk: RiskAssessment
    decision_readiness: str
    readiness_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketEvidence:
    symbol: str
    latest: float | None
    return_1d: float | None
    return_5d: float | None
    return_20d: float | None
    medium_term_trend: str
    short_term_state: str
    detection_reason: str
    return_zscore: float | None = None
    atr_multiple: float | None = None
    historical_percentile: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    drawdown_from_high: float | None = None
    sma_50_slope_20d: float | None = None
    evidence_ref: str = ""

    @property
    def absolute_move_z_score_60d(self) -> float | None:
        return self.return_zscore

    @property
    def absolute_move_percentile_252d(self) -> float | None:
        return self.historical_percentile

    @property
    def drawdown_from_252d_high(self) -> float | None:
        return self.drawdown_from_high


@dataclass(frozen=True)
class StrategyCondition:
    metric: str
    operator: str
    expected: bool | float | str


@dataclass(frozen=True)
class StrategyRuleDefinition:
    rule_id: str
    symbol: str
    action: str
    priority: int
    enabled: bool
    blocking: bool
    conditions: tuple[StrategyCondition, ...] = ()


@dataclass(frozen=True)
class StrategyConditionResult:
    metric: str
    operator: str
    expected: bool | float | str
    observed: bool | float | str | None
    status: str
    reason: str
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class StrategyRuleResult:
    name: str
    status: str
    observed: str
    threshold: str
    reason: str
    return_zscore: float | None = None
    atr_multiple: float | None = None
    historical_percentile: float | None = None
    evidence_refs: tuple[str, ...] = ()
    rule_id: str = ""
    symbol: str = ""
    action: str = ""
    priority: int = 0
    blocking: bool = False
    condition_results: tuple[StrategyConditionResult, ...] = ()

    @property
    def absolute_move_z_score_60d(self) -> float | None:
        return self.return_zscore

    @property
    def absolute_move_percentile_252d(self) -> float | None:
        return self.historical_percentile


@dataclass(frozen=True)
class ActionReadiness:
    status: str
    candidate_action: str | None
    symbol: str | None
    rule_id: str | None
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()
    human_approval_required: bool = True


@dataclass(frozen=True)
class ExecutionReadiness:
    status: str
    proposed_amount: float | None
    currency: str | None
    sizing_method: str | None
    reasons: tuple[str, ...]
    human_approval_required: bool = True


@dataclass(frozen=True)
class StrategyDecisionState:
    rules: tuple[StrategyRuleResult, ...]
    action_readiness: ActionReadiness
    execution_readiness: ExecutionReadiness = field(
        default_factory=lambda: ExecutionReadiness(
            "blocked",
            None,
            None,
            None,
            ("human_approval_required",),
        )
    )


@dataclass(frozen=True)
class DecisionHistoryRecord:
    report_date: date
    readiness_status: str
    candidate_action: str | None
    symbol: str | None
    rule_id: str | None
    rule_states: dict[str, str]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketBreadth:
    tracked_count: int
    above_50d_count: int
    above_200d_count: int
    above_50d_share: float | None
    above_200d_share: float | None
    rsp_vs_spy_20d: float | None
    vix_level: float | None
    vix_percentile: float | None

    @property
    def vix_level_percentile_252d(self) -> float | None:
        return self.vix_percentile


@dataclass(frozen=True)
class FxCostComparison:
    fx_date: date
    pair: str
    effective_rate: float
    all_in_rate: float
    spot_rate: float | None
    spot_premium: float | None
    benchmark_note: str


@dataclass(frozen=True)
class FxState:
    status: str
    usd_balance: float
    usd_required_daily: float | None
    coverage_days: float | None
    spot_usd_cnh: float | None
    cost_basis: float | None
    difference_pct: float | None
    reasons: tuple[str, ...] = ()
    comparisons: tuple[FxCostComparison, ...] = ()
    coverage_status: str = "unavailable"


@dataclass(frozen=True)
class GptAnalysisTask:
    question: str
    evidence_refs: tuple[str, ...]
    expected_output: str
    confidence_requirement: str
    task_id: str = ""
    status: str = "ready"
    blocked_reasons: tuple[str, ...] = ()

    @property
    def blocked_reason(self) -> str:
        return "; ".join(self.blocked_reasons)


@dataclass(frozen=True)
class CapabilityState:
    status: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportCapabilities:
    market_analysis: CapabilityState
    macro_analysis: CapabilityState
    portfolio_analysis: CapabilityState
    investment_action: CapabilityState
    fx_analysis: CapabilityState
    news_analysis: CapabilityState


@dataclass(frozen=True)
class DataQualityState:
    overall: CapabilityState
    capabilities: ReportCapabilities


@dataclass(frozen=True)
class MarketState:
    risk: str
    regime: str
    actionability: str
    reason: str


@dataclass(frozen=True)
class PortfolioDecisionState:
    risk: str
    data_readiness: str
    actionability: str
    reason: str


@dataclass(frozen=True)
class NewsState:
    quality: str
    actionability: str
    reason: str


@dataclass(frozen=True)
class ReportUseStates:
    market: MarketState
    portfolio: PortfolioDecisionState
    news: NewsState
    data_quality: DataQualityState | None = None


@dataclass(frozen=True)
class ReportState:
    data_quality_status: str
    market_actionability: str
    market_regime: str
    market_risk_score: int
    market_risk_level: str
    portfolio_risk: str
    portfolio_data_readiness: str
    portfolio_actionability: str
    portfolio_exposure_risk_score: int
    portfolio_exposure_risk_level: str
    portfolio_data_quality_risk_score: int
    portfolio_data_quality_risk_level: str
    news_quality: str
    news_actionability: str
    triggered_rules: tuple[str, ...]
    medium_term_trends: tuple[str, ...]
    portfolio_gaps: tuple[str, ...]
    capabilities: dict[str, str] = field(default_factory=dict)
    invested_allocation: dict[str, float | None] = field(default_factory=dict)
    liquid_asset_allocation_status: str = "unavailable"
    liquid_asset_allocation_reason: str = ""
    liquid_asset_allocation: dict[str, float | None] = field(default_factory=dict)
    fx_status: str = "unavailable"
    fx_spot_usd_cnh: float | None = None
    fx_cost_basis: float | None = None
    fx_difference_pct: float | None = None
    action_readiness_status: str = "blocked"
    candidate_action: str | None = None
    candidate_symbol: str | None = None
    candidate_rule_id: str | None = None
    execution_readiness_status: str = "blocked"
    proposed_action_amount: float | None = None
    proposed_action_currency: str | None = None
    portfolio_factor_exposures: dict[str, float | None] = field(
        default_factory=dict
    )
    portfolio_impact_scores: dict[str, int] = field(default_factory=dict)
    strategy_rule_states: dict[str, str] = field(default_factory=dict)
    gpt_task_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    publisher: str | None
    published_at: datetime | None
    related_symbol: str
    source: str
    query_symbol: str | None = None
    entity_kind: str | None = None
    entity_confidence: float = 0.0
    entity_match_reason: str = ""


@dataclass(frozen=True)
class AssetEntity:
    symbol: str
    name: str
    entity_kind: Literal["etf", "company", "index", "commodity"]
    aliases: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NewsQualityGate:
    entity_precision: float | None
    precision_threshold: float
    status: str
    news_score: float | None
    fundamental_score: float | None
    portfolio_action: str
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EntityLinkResult:
    linked_items: list[NewsItem]
    rejected_items: list[NewsItem]
    gate: NewsQualityGate


@dataclass(frozen=True)
class NewsCluster:
    topic: str
    related_assets: list[str]
    representative_headlines: list[str]
    source_urls: list[str]
    item_count: int
    confidence: float
    source_count: int = 0
    why_it_matters: str = ""
    manual_read_urls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FundamentalEvent:
    event_type: str
    related_symbol: str
    headline: str
    publisher: str | None
    source_url: str
    confidence: float
    review_type: str = ""
    why_it_matters: str = ""


@dataclass(frozen=True)
class CompanyEvent:
    event_type: Literal[
        "earnings_release",
        "guidance_change",
        "buyback",
        "dividend_change",
        "management_change",
        "regulatory_event",
    ]
    related_symbol: str
    headline: str
    publisher: str | None
    source_urls: list[str]
    confidence: float
    article_count: int
    event_date: str
    review_type: str = "company_event_review"
    why_it_matters: str = "Company event requires primary-source review."

    @property
    def source_url(self) -> str:
        return self.source_urls[0] if self.source_urls else ""


@dataclass(frozen=True)
class EtfEvent:
    event_type: Literal[
        "fee_change",
        "distribution_change",
        "methodology_change",
        "rebalance",
        "flow_event",
    ]
    related_symbol: str
    headline: str
    publisher: str | None
    source_urls: list[str]
    confidence: float
    article_count: int
    event_date: str
    review_type: str = "etf_event_review"
    why_it_matters: str = "ETF event requires fund-specific review."

    @property
    def source_url(self) -> str:
        return self.source_urls[0] if self.source_urls else ""


@dataclass(frozen=True)
class IndexEvent:
    event_type: Literal["methodology_change", "constituent_change", "rebalance"]
    related_symbol: str
    headline: str
    publisher: str | None
    source_urls: list[str]
    confidence: float
    article_count: int
    event_date: str
    review_type: str = "index_event_review"
    why_it_matters: str = "Index event requires methodology or constituent review."

    @property
    def source_url(self) -> str:
        return self.source_urls[0] if self.source_urls else ""


@dataclass(frozen=True)
class CommodityEvent:
    event_type: Literal["supply_disruption", "inventory_change", "policy_event"]
    related_symbol: str
    headline: str
    publisher: str | None
    source_urls: list[str]
    confidence: float
    article_count: int
    event_date: str
    review_type: str = "commodity_event_review"
    why_it_matters: str = "Commodity event requires supply, inventory, or policy review."

    @property
    def source_url(self) -> str:
        return self.source_urls[0] if self.source_urls else ""


AssetEvent = CompanyEvent | EtfEvent | IndexEvent | CommodityEvent
