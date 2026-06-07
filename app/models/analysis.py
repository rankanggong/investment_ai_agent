from dataclasses import dataclass


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

