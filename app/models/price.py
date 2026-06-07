from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    adjusted_close: float | None
    volume: float | None
    source: str

