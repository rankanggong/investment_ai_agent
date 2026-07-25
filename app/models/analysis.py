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
class PortfolioSummary:
    base_currency: str
    total_holding_cost: float | None
    allocations: list[PortfolioAllocation]
    daily_investment_budget: float | None
    usd_cash: float
    usd_daily_spend: float | None
    usd_coverage_days: float | None
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    level: str
    explanations: list[str]


@dataclass(frozen=True)
class MarketEvidence:
    symbol: str
    latest: float | None
    return_1d: float | None
    return_5d: float | None
    return_20d: float | None
    structural_trend: str
    short_term_state: str
    detection_reason: str


@dataclass(frozen=True)
class StrategyRuleResult:
    name: str
    status: str
    observed: str
    threshold: str
    reason: str


@dataclass(frozen=True)
class ReportState:
    executive_status: str
    data_quality_status: str
    macro_regime: str
    risk_score: int
    risk_level: str
    triggered_rules: tuple[str, ...]
    structural_trends: tuple[str, ...]
    portfolio_gaps: tuple[str, ...]


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
