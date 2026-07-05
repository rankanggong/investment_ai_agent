from app.models.analysis import (
    DataCoverage,
    FundamentalEvent,
    MacroContext,
    ManualReadItem,
    NewsCluster,
    PriceSignal,
    ReportSignals,
    SectorRotation,
    SignalInsight,
    WatchNextItem,
)


def analyze_report_signals(
    price_signals: dict[str, PriceSignal],
    sector_rotation: SectorRotation,
    macro_context: MacroContext | None,
    news_clusters: list[NewsCluster],
    fundamental_events: list[FundamentalEvent],
    data_coverage: DataCoverage | None = None,
) -> ReportSignals:
    insights: list[SignalInsight] = []
    watch_next: list[WatchNextItem] = []
    manual_reading: list[ManualReadItem] = []

    for signal in price_signals.values():
        if not signal.is_unusual_move:
            continue
        insights.append(_price_insight(signal))
        watch_next.append(_price_watch_item(signal))

    for symbol in sector_rotation.strong_sectors:
        insights.append(_sector_insight(symbol, "relative_strength"))
        watch_next.append(_sector_watch_item(symbol, "leadership broadens into related growth assets"))
    for symbol in sector_rotation.weak_sectors:
        insights.append(_sector_insight(symbol, "relative_weakness"))
        watch_next.append(_sector_watch_item(symbol, "weakness remains isolated instead of spreading"))

    if macro_context is not None:
        for row in macro_context.evidence_rows:
            if row.signal in {"mixed", "unknown"}:
                continue
            insights.append(_macro_insight(row.area, row.signal, row.evidence, row.interpretation))
            watch_next.append(_macro_watch_item(row.area, row.signal))

    for cluster in news_clusters:
        insights.append(_news_insight(cluster))
        watch_next.append(_news_watch_item(cluster))
        manual_reading.extend(_manual_reads_from_cluster(cluster))

    for event in fundamental_events:
        insights.append(_fundamental_insight(event))
        watch_next.append(_fundamental_watch_item(event))
        manual_reading.append(_manual_read_from_event(event))

    if data_coverage is not None:
        for row in data_coverage.rows:
            if row.status == "available":
                continue
            insights.append(_data_gap_insight(row.category, row.item, row.status, row.detail))
            watch_next.append(_data_gap_watch_item(row.category, row.item))

    return ReportSignals(
        insights=insights,
        watch_next=_dedupe_watch_items(watch_next),
        manual_reading=sorted(
            _dedupe_manual_reading(manual_reading),
            key=lambda item: (-item.priority, item.related_symbol, item.title),
        ),
    )


def _price_insight(signal: PriceSignal) -> SignalInsight:
    evidence = ["price_confirmed"]
    if signal.volume_ratio_20d is not None and signal.volume_ratio_20d > 2:
        evidence.append("volume_confirmed")
    return SignalInsight(
        subject=signal.symbol,
        observed_fact=f"{signal.symbol} moved {_format_percent(signal.return_1d)} in 1D.",
        trigger_type="absolute_move",
        evidence_type=evidence,
        interpretation=signal.reason or "Unusual price move detected by deterministic thresholds.",
        confidence="medium",
        uncertainty="No confirmed fundamental event is linked to the move.",
        watch_next=f"Whether {signal.symbol} confirms the move with follow-through and stable volume.",
        invalidation=f"{signal.symbol} gives back the unusual move without related confirmation.",
    )


def _price_watch_item(signal: PriceSignal) -> WatchNextItem:
    return WatchNextItem(
        subject=signal.symbol,
        watch=f"Whether {signal.symbol} follow-through confirms the unusual move.",
        confirmation="Move persists and volume remains above recent average.",
        invalidation=f"{signal.symbol} gives back the move while volume normalizes.",
        source="price",
    )


def _sector_insight(symbol: str, trigger_type: str) -> SignalInsight:
    direction = "strength" if trigger_type == "relative_strength" else "weakness"
    evidence_type = (
        ["relative_strength_confirmed"]
        if trigger_type == "relative_strength"
        else ["relative_weakness_confirmed"]
    )
    return SignalInsight(
        subject=symbol,
        observed_fact=f"{symbol} appeared in sector rotation {direction}.",
        trigger_type=trigger_type,
        evidence_type=evidence_type,
        interpretation=f"{symbol} is part of current sector rotation {direction}.",
        confidence="medium",
        uncertainty="Sector rotation does not by itself confirm a fundamental change.",
        watch_next=f"Whether {symbol} {direction} persists versus SPY.",
        invalidation=f"{symbol} stops outperforming or underperforming SPY.",
    )


def _sector_watch_item(symbol: str, confirmation: str) -> WatchNextItem:
    return WatchNextItem(
        subject=symbol,
        watch=f"Whether {symbol} rotation signal persists versus SPY.",
        confirmation=confirmation,
        invalidation=f"{symbol} relative performance returns to neutral.",
        source="sector_rotation",
    )


def _macro_insight(area: str, signal: str, evidence: str, interpretation: str) -> SignalInsight:
    return SignalInsight(
        subject=area,
        observed_fact=evidence,
        trigger_type="macro_proxy_shift",
        evidence_type=["macro_supported"],
        interpretation=interpretation,
        confidence="medium",
        uncertainty="ETF proxies are not a substitute for formal macro data.",
        watch_next=f"Whether {area} proxy evidence continues to support {signal}.",
        invalidation=f"{area} proxy evidence moves back to mixed.",
    )


def _macro_watch_item(area: str, signal: str) -> WatchNextItem:
    return WatchNextItem(
        subject=area,
        watch=f"Whether {area} proxy evidence confirms {signal}.",
        confirmation=f"{area} remains in {signal} on the next report.",
        invalidation=f"{area} returns to mixed or unknown.",
        source="macro_context",
    )


def _news_insight(cluster: NewsCluster) -> SignalInsight:
    subject = _first_asset(cluster.related_assets)
    return SignalInsight(
        subject=subject,
        observed_fact=f"{cluster.item_count} stored news items grouped under {cluster.topic}.",
        trigger_type="news_cluster",
        evidence_type=["news_supported"],
        interpretation=cluster.why_it_matters or "News cluster may explain asset-specific attention.",
        confidence=_confidence_label(cluster.confidence),
        uncertainty="Stored headlines need manual review before treating them as fundamental evidence.",
        watch_next=f"Whether price action in {subject} confirms the news cluster.",
        invalidation=f"{subject} price action does not confirm the news cluster.",
    )


def _news_watch_item(cluster: NewsCluster) -> WatchNextItem:
    subject = _first_asset(cluster.related_assets)
    return WatchNextItem(
        subject=subject,
        watch=f"Whether {subject} price action confirms the {cluster.topic} news cluster.",
        confirmation="Related asset shows follow-through or relative strength.",
        invalidation="Related asset does not react despite continued headlines.",
        source="news_cluster",
    )


def _fundamental_insight(event: FundamentalEvent) -> SignalInsight:
    return SignalInsight(
        subject=event.related_symbol,
        observed_fact=f"{event.related_symbol} had a {event.event_type}: {event.headline}",
        trigger_type="fundamental_event",
        evidence_type=["fundamental_confirmed", "manual_review_required"],
        interpretation=event.why_it_matters or "This event may affect fundamental assumptions.",
        confidence=_confidence_label(event.confidence),
        uncertainty="The source should be read manually before changing assumptions.",
        watch_next=f"Manual review of {event.related_symbol} {event.review_type or event.event_type}.",
        invalidation="Primary-source details show the headline is not material.",
    )


def _fundamental_watch_item(event: FundamentalEvent) -> WatchNextItem:
    return WatchNextItem(
        subject=event.related_symbol,
        watch=f"Read the source for {event.related_symbol} {event.review_type or event.event_type}.",
        confirmation="Primary-source details confirm a material assumption change.",
        invalidation="Primary-source details show limited or no material impact.",
        source="fundamental_event",
    )


def _data_gap_insight(category: str, item: str, status: str, detail: str) -> SignalInsight:
    return SignalInsight(
        subject=f"{category}: {item}",
        observed_fact=detail,
        trigger_type="data_gap",
        evidence_type=["data_limited"],
        interpretation=f"{category} {item} data is {status}.",
        confidence="high",
        data_coverage=status,
        uncertainty="Quiet output may reflect missing or insufficient data.",
        watch_next=f"Whether {category} {item} becomes available after the next collection run.",
        invalidation=f"{category} {item} data becomes available.",
    )


def _data_gap_watch_item(category: str, item: str) -> WatchNextItem:
    return WatchNextItem(
        subject=f"{category}: {item}",
        watch=f"Whether {category} {item} data becomes available after the next collection run.",
        confirmation="Data coverage changes to available.",
        invalidation="Data remains missing or insufficient.",
        source="data_coverage",
    )


def _manual_reads_from_cluster(cluster: NewsCluster) -> list[ManualReadItem]:
    subject = _first_asset(cluster.related_assets)
    urls = cluster.manual_read_urls or cluster.source_urls
    return [
        ManualReadItem(
            title=f"{cluster.topic} news cluster",
            url=url,
            reason=cluster.why_it_matters or "Manual review can confirm whether the cluster matters.",
            source_type="news_cluster",
            related_symbol=subject,
            priority=80,
        )
        for url in urls
    ]


def _manual_read_from_event(event: FundamentalEvent) -> ManualReadItem:
    return ManualReadItem(
        title=event.headline,
        url=event.source_url,
        reason=event.why_it_matters or "Manual review can confirm whether the event is material.",
        source_type=event.review_type or event.event_type,
        related_symbol=event.related_symbol,
        priority=100,
    )


def _dedupe_watch_items(items: list[WatchNextItem]) -> list[WatchNextItem]:
    seen: set[tuple[str, str, str]] = set()
    result: list[WatchNextItem] = []
    for item in items:
        key = (item.subject, item.watch, item.source)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_manual_reading(items: list[ManualReadItem]) -> list[ManualReadItem]:
    best_by_url: dict[str, ManualReadItem] = {}
    for item in items:
        existing = best_by_url.get(item.url)
        if existing is not None and existing.priority >= item.priority:
            continue
        best_by_url[item.url] = item
    return list(best_by_url.values())


def _first_asset(assets: list[str]) -> str:
    if not assets:
        return "Market"
    return assets[0].upper()


def _confidence_label(value: float) -> str:
    if value >= 0.8:
        return "high"
    if value >= 0.55:
        return "medium"
    return "low"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"
