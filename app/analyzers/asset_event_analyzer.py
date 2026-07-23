from collections import OrderedDict
import re

from app.models.analysis import (
    AssetEvent,
    CommodityEvent,
    CompanyEvent,
    EtfEvent,
    IndexEvent,
    NewsItem,
)


MIN_ENTITY_CONFIDENCE = 0.80


def analyze_asset_events(
    items: list[NewsItem],
    max_events: int = 10,
) -> list[AssetEvent]:
    """Classify linked articles with an asset-specific schema and dedupe events."""
    grouped: OrderedDict[tuple[str, str, str, str], list[NewsItem]] = OrderedDict()
    for item in items:
        if item.entity_confidence < MIN_ENTITY_CONFIDENCE or item.entity_kind is None:
            continue
        event_type = _event_type(item)
        if event_type is None:
            continue
        event_date = item.published_at.date().isoformat() if item.published_at else "unknown"
        key = (item.entity_kind, item.related_symbol.upper(), event_type, event_date)
        grouped.setdefault(key, []).append(item)

    events = [
        _build_event(entity_kind, symbol, event_type, event_date, articles)
        for (entity_kind, symbol, event_type, event_date), articles in grouped.items()
    ]
    return events[:max_events]


def _event_type(item: NewsItem) -> str | None:
    if item.entity_kind == "company":
        return _company_event_type(item.title)
    if item.entity_kind == "etf":
        return _etf_event_type(item)
    if item.entity_kind == "index":
        return _index_event_type(item.title)
    if item.entity_kind == "commodity":
        return _commodity_event_type(item.title)
    return None


def _company_event_type(title: str) -> str | None:
    normalized = title.casefold()
    patterns = [
        ("guidance_change", r"\b(guidance|outlook|forecast)\b"),
        ("earnings_release", r"\b(earnings|quarterly results|quarterly profit|revenue)\b"),
        ("buyback", r"\b(buyback|repurchase)\b"),
        ("dividend_change", r"\b(dividend|payout)\b"),
        ("management_change", r"\b(ceo|cfo|resigns|appoints|appointed)\b"),
        ("regulatory_event", r"\b(probe|lawsuit|antitrust|sec|regulator)\b"),
    ]
    return _first_match(normalized, patterns)


def _etf_event_type(item: NewsItem) -> str | None:
    normalized = item.title.casefold()
    if re.search(r"\b(fee|expense ratio)\b", normalized) and re.search(
        r"\b(cut|cuts|raise|raises|change|changes|announces|announced)\b", normalized
    ):
        return "fee_change"
    if re.search(r"\b(methodology|index provider)\b", normalized):
        return "methodology_change"
    if re.search(r"\b(rebalance|rebalancing)\b", normalized):
        return "rebalance"
    if re.search(r"\b(inflow|outflow|fund flow)\b", normalized):
        return "flow_event"
    if _entity_is_subject(item) and re.search(r"\b(distribution|dividend)\b", normalized) and re.search(
        r"\b(cut|cuts|raise|raises|change|changes|announces|announced)\b", normalized
    ):
        return "distribution_change"
    return None


def _index_event_type(title: str) -> str | None:
    normalized = title.casefold()
    return _first_match(
        normalized,
        [
            ("constituent_change", r"\b(adds|removes|constituent change)\b"),
            ("methodology_change", r"\b(methodology|rule change)\b"),
            ("rebalance", r"\b(rebalance|rebalancing)\b"),
        ],
    )


def _commodity_event_type(title: str) -> str | None:
    normalized = title.casefold()
    return _first_match(
        normalized,
        [
            ("supply_disruption", r"\b(supply disruption|production cut|mine closure|embargo)\b"),
            ("inventory_change", r"\b(inventory|stockpile)\b"),
            ("policy_event", r"\b(tariff|sanction|export ban|policy)\b"),
        ],
    )


def _first_match(normalized: str, patterns: list[tuple[str, str]]) -> str | None:
    for event_type, pattern in patterns:
        if re.search(pattern, normalized):
            return event_type
    return None


def _entity_is_subject(item: NewsItem) -> bool:
    prefix = item.title[: max(24, len(item.related_symbol) + 8)]
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9]){re.escape(item.related_symbol)}(?![A-Za-z0-9])",
            prefix,
        )
    )


def _build_event(
    entity_kind: str,
    symbol: str,
    event_type: str,
    event_date: str,
    articles: list[NewsItem],
) -> AssetEvent:
    first = articles[0]
    common = dict(
        event_type=event_type,
        related_symbol=symbol,
        headline=first.title,
        publisher=first.publisher,
        source_urls=[article.url for article in articles],
        confidence=min(1.0, max(article.entity_confidence for article in articles)),
        article_count=len(articles),
        event_date=event_date,
    )
    if entity_kind == "company":
        return CompanyEvent(**common)
    if entity_kind == "etf":
        return EtfEvent(**common)
    if entity_kind == "index":
        return IndexEvent(**common)
    return CommodityEvent(**common)
