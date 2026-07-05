from dataclasses import dataclass, field
from datetime import datetime


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
class NewsItem:
    title: str
    url: str
    publisher: str | None
    published_at: datetime | None
    related_symbol: str
    source: str


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
