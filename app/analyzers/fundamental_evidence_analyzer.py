from collections import defaultdict
from datetime import date

from app.config import FundamentalPolicy
from app.models.analysis import (
    EarningsEstimateObservation,
    EarningsRevision,
    FundamentalEvidenceState,
    ValuationObservation,
)


def analyze_fundamental_evidence(
    valuations: list[ValuationObservation],
    estimates: list[EarningsEstimateObservation],
    policy: FundamentalPolicy,
    report_date: date,
) -> FundamentalEvidenceState:
    """Select current observations and derive like-for-like estimate revisions."""
    latest_valuations = _latest_valuations(valuations, report_date)
    revisions = _earnings_revisions(
        estimates, policy.earnings_revision_materiality, report_date
    )
    reasons: list[str] = []
    valuation_status = _evidence_status(
        [row.as_of_date for row in latest_valuations],
        policy.valuation_stale_after_days,
        report_date,
        "valuation",
        reasons,
    )
    revision_status = _evidence_status(
        [row.current_date for row in revisions],
        policy.earnings_revision_stale_after_days,
        report_date,
        "earnings_revision",
        reasons,
    )
    if estimates and not revisions:
        reasons.append("earnings_revision_requires_two_like_for_like_observations")
        revision_status = "blocked"
    if policy.earnings_revision_materiality is None:
        reasons.append("earnings_revision_materiality_not_configured")
        if revision_status == "available":
            revision_status = "degraded"
    if any(row.asset_type == "unknown" for row in latest_valuations):
        reasons.append("valuation_asset_type_missing")
        if valuation_status == "available":
            valuation_status = "degraded"
    if any(row.asset_type == "unknown" for row in revisions):
        reasons.append("earnings_revision_asset_type_missing")
        if revision_status == "available":
            revision_status = "degraded"
    flags = _revision_flags(revisions)
    return FundamentalEvidenceState(
        valuation_status,
        revision_status,
        tuple(latest_valuations),
        tuple(revisions),
        flags,
        tuple(dict.fromkeys(reasons)),
    )


def _latest_valuations(
    observations: list[ValuationObservation],
    report_date: date,
) -> list[ValuationObservation]:
    latest: dict[tuple[str, str, str, str], ValuationObservation] = {}
    for row in observations:
        if row.as_of_date > report_date:
            continue
        key = (row.symbol, row.asset_type, row.metric, row.source)
        if key not in latest or row.as_of_date > latest[key].as_of_date:
            latest[key] = row
    return sorted(latest.values(), key=lambda row: (row.symbol, row.metric, row.source))


def _earnings_revisions(
    observations: list[EarningsEstimateObservation],
    materiality: float | None,
    report_date: date,
) -> list[EarningsRevision]:
    grouped: dict[
        tuple[str, str, str, str, str], list[EarningsEstimateObservation]
    ] = defaultdict(list)
    for row in observations:
        if row.as_of_date > report_date:
            continue
        grouped[
            (row.symbol, row.asset_type, row.fiscal_period, row.metric, row.source)
        ].append(row)
    revisions: list[EarningsRevision] = []
    for (symbol, asset_type, period, metric, source), rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: row.as_of_date)
        if len(ordered) < 2:
            continue
        previous, current = ordered[-2:]
        change_pct = (
            current.value / previous.value - 1
            if previous.value != 0
            else None
        )
        direction = (
            "positive"
            if current.value > previous.value
            else "negative"
            if current.value < previous.value
            else "unchanged"
        )
        revisions.append(
            EarningsRevision(
                symbol,
                period,
                metric,
                previous.as_of_date,
                current.as_of_date,
                previous.value,
                current.value,
                change_pct,
                direction,
                (
                    abs(change_pct) >= materiality
                    if change_pct is not None and materiality is not None
                    else None
                ),
                source,
                asset_type,
            )
        )
    return revisions


def _evidence_status(
    dates: list[date],
    stale_after_days: int | None,
    report_date: date,
    prefix: str,
    reasons: list[str],
) -> str:
    if not dates:
        reasons.append(f"{prefix}_data_not_supplied")
        return "blocked"
    if stale_after_days is None:
        reasons.append(f"{prefix}_freshness_threshold_not_configured")
        return "degraded"
    if any((report_date - item).days > stale_after_days for item in dates):
        reasons.append(f"{prefix}_data_stale")
        return "degraded"
    return "available"


def _revision_flags(revisions: list[EarningsRevision]) -> dict[str, bool]:
    grouped: dict[str, list[EarningsRevision]] = defaultdict(list)
    for row in revisions:
        grouped[row.symbol].append(row)
    flags: dict[str, bool] = {}
    for symbol, rows in grouped.items():
        if any(row.material is None for row in rows):
            continue
        flags[f"{symbol}.earnings_revision_negative"] = any(
            row.direction == "negative" and row.material is True
            for row in rows
        )
    return flags
