import csv
from dataclasses import dataclass
from datetime import date
import math
from pathlib import Path

from app.models.analysis import (
    EarningsEstimateObservation,
    ValuationObservation,
)


_VALUATION_METRICS = {
    "equity": {
        "forward_pe", "trailing_pe", "price_to_book", "price_to_sales",
        "ev_to_ebitda",
    },
    "etf": {"forward_pe", "trailing_pe", "price_to_book", "distribution_yield"},
    "index": {"forward_pe", "trailing_pe", "price_to_book", "earnings_yield"},
    "commodity": {"spot_premium"},
}
_EARNINGS_METRICS = {
    "equity": {"eps", "revenue", "ebitda"},
    "etf": {"eps", "eps_growth", "revenue_growth"},
    "index": {"eps", "eps_growth", "revenue_growth"},
    "commodity": set(),
}


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
            asset_type = (row.get("asset_type") or "").strip().lower()
            if not symbol or not metric or not source or not asset_type:
                raise ValueError(
                    f"line {line_number}: symbol, asset_type, metric, and source are required"
                )
            if asset_type not in _VALUATION_METRICS:
                raise ValueError(
                    f"line {line_number}: unsupported asset_type {asset_type!r}"
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
                _validate_metric(
                    line_number, record_type, asset_type, metric,
                    _VALUATION_METRICS,
                )
                valuations.append(
                    ValuationObservation(
                        symbol, as_of_date, metric, value, source,
                        (row.get("currency") or "").strip().upper() or None,
                        (row.get("period") or "").strip() or None,
                        asset_type,
                    )
                )
            elif record_type == "earnings_estimate":
                _validate_metric(
                    line_number, record_type, asset_type, metric,
                    _EARNINGS_METRICS,
                )
                fiscal_period = (row.get("period") or "").strip()
                if not fiscal_period:
                    raise ValueError(
                        f"line {line_number}: earnings estimate period is required"
                    )
                estimates.append(
                    EarningsEstimateObservation(
                        symbol, as_of_date, fiscal_period, metric, value, source,
                        asset_type,
                    )
                )
            else:
                raise ValueError(
                    f"line {line_number}: unsupported record_type {record_type!r}"
                )
    return FundamentalImport(valuations, estimates)


def _validate_metric(
    line_number: int,
    record_type: str,
    asset_type: str,
    metric: str,
    schemas: dict[str, set[str]],
) -> None:
    if metric not in schemas[asset_type]:
        raise ValueError(
            f"line {line_number}: metric {metric!r} is not valid for "
            f"{asset_type} {record_type}"
        )
