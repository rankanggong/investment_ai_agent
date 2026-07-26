from dataclasses import replace
import re

from app.models.analysis import (
    AssetEntity,
    EntityLinkResult,
    NewsItem,
    NewsQualityGate,
)


DEFAULT_ENTITY_PRECISION_THRESHOLD = 0.80
MIN_ENTITY_LINK_CONFIDENCE = 0.80


def link_news_entities(
    items: list[NewsItem],
    entities: list[AssetEntity],
    precision_threshold: float = DEFAULT_ENTITY_PRECISION_THRESHOLD,
) -> EntityLinkResult:
    """Link candidate articles to asset entities and fail closed on low precision."""
    entities_by_symbol = {entity.symbol.upper(): entity for entity in entities}
    linked: list[NewsItem] = []
    rejected: list[NewsItem] = []

    for item in _deduplicate_candidates(items):
        query_symbol = (item.query_symbol or item.related_symbol).upper()
        entity = entities_by_symbol.get(query_symbol)
        if entity is None:
            rejected.append(
                replace(
                    item,
                    query_symbol=query_symbol,
                    entity_confidence=0.0,
                    entity_match_reason="query symbol is not in the entity registry",
                )
            )
            continue

        confidence, reason = _match_entity(item.title, entity)
        classified = replace(
            item,
            related_symbol=entity.symbol.upper(),
            query_symbol=query_symbol,
            entity_kind=entity.entity_kind,
            entity_confidence=confidence,
            entity_match_reason=reason,
        )
        if confidence >= MIN_ENTITY_LINK_CONFIDENCE:
            linked.append(classified)
        else:
            rejected.append(classified)

    total = len(linked) + len(rejected)
    precision = len(linked) / total if total else None
    gate = _quality_gate(precision, precision_threshold)
    return EntityLinkResult(linked_items=linked, rejected_items=rejected, gate=gate)


def _match_entity(title: str, entity: AssetEntity) -> tuple[float, str]:
    symbol = entity.symbol.upper()
    for alias in [entity.name, *entity.aliases]:
        if alias == symbol:
            continue
        if alias and _contains_phrase(title, alias):
            return 0.99, f"title contains entity name or alias: {alias}"

    if re.search(rf"(?<![A-Za-z0-9]){re.escape(symbol)}(?![A-Za-z0-9])", title):
        return 0.95, f"title contains exact uppercase ticker: {symbol}"

    if re.search(rf"(?<![A-Za-z0-9]){re.escape(symbol.lower())}(?![A-Za-z0-9])", title.lower()):
        return 0.20, "title contains only an ambiguous case-insensitive ticker token"

    return 0.0, "query origin is not entity-link evidence"


def _contains_phrase(title: str, phrase: str) -> bool:
    normalized_title = " ".join(title.casefold().split())
    normalized_phrase = " ".join(phrase.casefold().split())
    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_phrase)}(?![a-z0-9])",
            normalized_title,
        )
    )


def _deduplicate_candidates(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    result: list[NewsItem] = []
    for item in items:
        key = item.url or " ".join(item.title.casefold().split())
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _quality_gate(
    entity_precision: float | None,
    precision_threshold: float,
) -> NewsQualityGate:
    if entity_precision is None:
        return NewsQualityGate(
            entity_precision=None,
            precision_threshold=precision_threshold,
            status="disabled",
            news_score=None,
            fundamental_score=None,
            portfolio_action="unavailable",
            reasons=["No candidate news was supplied."],
        )
    if entity_precision < precision_threshold:
        return NewsQualityGate(
            entity_precision=entity_precision,
            precision_threshold=precision_threshold,
            status="data_quality_review",
            news_score=None,
            fundamental_score=None,
            portfolio_action="unavailable",
            reasons=[
                f"Entity precision {entity_precision:.2%} is below threshold "
                f"{precision_threshold:.2%}."
            ],
        )
    return NewsQualityGate(
        entity_precision=entity_precision,
        precision_threshold=precision_threshold,
        status="available",
        news_score=None,
        fundamental_score=None,
        portfolio_action="unavailable",
        reasons=[],
    )
