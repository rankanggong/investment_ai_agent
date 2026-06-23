from dataclasses import dataclass
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
class MacroContext:
    rates_context: str
    usd_context: str
    credit_context: str
    gold_context: str
    overall_regime: str
    notes: list[str]


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
