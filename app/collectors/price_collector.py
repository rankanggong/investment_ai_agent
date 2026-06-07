import csv
from datetime import date
from pathlib import Path

from app.models.price import PriceBar


def load_price_csv(path: Path, source: str = "csv") -> list[PriceBar]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [_row_to_bar(row, source) for row in reader]


def _row_to_bar(row: dict[str, str], source: str) -> PriceBar:
    return PriceBar(
        symbol=row["symbol"].upper(),
        date=date.fromisoformat(row["date"]),
        open=_optional_float(row.get("open")),
        high=_optional_float(row.get("high")),
        low=_optional_float(row.get("low")),
        close=float(row["close"]),
        adjusted_close=_optional_float(row.get("adjusted_close")),
        volume=_optional_float(row.get("volume")),
        source=source,
    )


def _optional_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)

