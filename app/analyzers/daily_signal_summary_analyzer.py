from app.models.analysis import (
    DailySignalSummary,
    FundamentalEvent,
    MacroContext,
    NewsCluster,
    PriceSignal,
    SectorRotation,
)

SECTOR_MONITOR_THRESHOLD = 0.35


def analyze_daily_signal_summary(
    price_signals: dict[str, PriceSignal],
    sector_rotation: SectorRotation,
    macro_context: MacroContext | None,
    news_clusters: list[NewsCluster],
    fundamental_events: list[FundamentalEvent],
) -> DailySignalSummary:
    unusual_count = sum(1 for signal in price_signals.values() if signal.is_unusual_move)
    cluster_count = len(news_clusters)
    event_count = len(fundamental_events)

    drivers = [
        _price_driver(unusual_count),
        _sector_driver(sector_rotation),
        _macro_driver(macro_context),
        _news_driver(cluster_count),
        _fundamental_driver(event_count),
    ]

    review_reasons: list[str] = []
    if unusual_count:
        review_reasons.append("price moves")
    if event_count:
        review_reasons.append("fundamental events")

    monitor_reasons: list[str] = []
    if _sector_needs_monitor(sector_rotation):
        monitor_reasons.append("sector rotation")
    if _macro_needs_monitor(macro_context):
        monitor_reasons.append("macro context")
    if cluster_count:
        monitor_reasons.append("news clusters")

    if review_reasons:
        return DailySignalSummary(
            status="review_required",
            drivers=drivers,
            reason=f"Review required because {_join_reasons(review_reasons)} crossed thresholds.",
        )

    if monitor_reasons:
        return DailySignalSummary(
            status="monitor",
            drivers=drivers,
            reason=f"Monitor because {_join_reasons(monitor_reasons)} crossed thresholds.",
        )

    return DailySignalSummary(
        status="no_material_signal",
        drivers=drivers,
        reason="No price, sector, macro, news, or fundamental event crossed review thresholds.",
    )


def _price_driver(unusual_count: int) -> str:
    if unusual_count == 0:
        return "Price: no unusual moves"
    return f"Price: {unusual_count} unusual {_plural('move', unusual_count)}"


def _sector_driver(sector_rotation: SectorRotation) -> str:
    if _sector_needs_monitor(sector_rotation):
        return f"Sector rotation: risk-on score {sector_rotation.risk_on_score:.2f}"
    if (
        sector_rotation.growth_vs_value == "unknown"
        and sector_rotation.cyclical_vs_defensive == "unknown"
    ):
        return "Sector rotation: unknown"
    return "Sector rotation: mixed"


def _macro_driver(macro_context: MacroContext | None) -> str:
    if macro_context is None:
        return "Macro: not available"
    if macro_context.overall_regime == "unknown":
        return "Macro: unknown"
    return f"Macro: {macro_context.overall_regime}"


def _news_driver(cluster_count: int) -> str:
    if cluster_count == 0:
        return "News: no important clusters"
    return f"News: {cluster_count} important {_plural('cluster', cluster_count)}"


def _fundamental_driver(event_count: int) -> str:
    if event_count == 0:
        return "Fundamental events: none detected"
    return f"Fundamental events: {event_count} detected"


def _sector_needs_monitor(sector_rotation: SectorRotation) -> bool:
    return abs(sector_rotation.risk_on_score) >= SECTOR_MONITOR_THRESHOLD


def _macro_needs_monitor(macro_context: MacroContext | None) -> bool:
    if macro_context is None:
        return False
    return macro_context.overall_regime not in {"mixed", "unknown"}


def _join_reasons(reasons: list[str]) -> str:
    if len(reasons) == 1:
        return reasons[0]
    return ", ".join(reasons[:-1]) + f" and {reasons[-1]}"


def _plural(word: str, count: int) -> str:
    if count == 1:
        return word
    return f"{word}s"
