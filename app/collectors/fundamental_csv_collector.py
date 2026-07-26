import csv
from dataclasses import dataclass
from datetime import date
import math
from pathlib import Path

from app.models.analysis import (
    EarningsEstimateObservation,
    ValuationObservation,
)


@dataclass(frozen=True)
class FundamentalImport:
    valuations: list[ValuationObservation]
    earnings_estimates: list[EarningsEstimateObservation]


def load_fundamental_csv(path: Path) -> FundamentalImport:
    valuations: list[ValuationObservation] = []
    estimates: list[EarningsEstimateObservation] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), 2):
            record_type = (row.get("record_type") or "").strip()
            symbol = (row.get("symbol") or "").strip().upper()
            metric = (row.get("metric") or "").strip()
            source = (row.get("source") or "").strip()
            if not symbol or not metric or not source:
                raise ValueError(
                    f"line {line_number}: symbol, metric, and source are required"
                )
            try:
                as_of_date = date.fromisoformat((row.get("as_of_date") or "").strip())
                value = float((row.get("value") or "").strip())
            except ValueError as error:
                raise ValueError(
                    f"line {line_number}: invalid as_of_date or value"
                ) from error
            if not math.isfinite(value):
                raise ValueError(f"line {line_number}: value must be finite")
            if record_type == "valuation":
                valuations.append(
                    ValuationObservation(
                        symbol, as_of_date, metric, value, source,
                        (row.get("currency") or "").strip().upper() or None,
                        (row.get("period") or "").strip() or None,
                    )
                )
            elif record_type == "earnings_estimate":
                fiscal_period = (row.get("period") or "").strip()
                if not fiscal_period:
                    raise ValueError(
                        f"line {line_number}: earnings estimate period is required"
                    )
                estimates.append(
                    EarningsEstimateObservation(
                        symbol, as_of_date, fiscal_period, metric, value, source
                    )
                )
            else:
                raise ValueError(
                    f"line {line_number}: unsupported record_type {record_type!r}"
                )
    return FundamentalImport(valuations, estimates)
