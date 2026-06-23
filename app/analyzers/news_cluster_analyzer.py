from collections import Counter, defaultdict
import re

from app.models.analysis import NewsCluster, NewsItem


STOPWORDS = {
    "after",
    "amid",
    "and",
    "are",
    "as",
    "for",
    "from",
    "into",
    "market",
    "markets",
    "news",
    "on",
    "over",
    "says",
    "stock",
    "stocks",
    "the",
    "to",
    "with",
}


def analyze_news_clusters(
    items: list[NewsItem],
    max_clusters: int = 5,
) -> list[NewsCluster]:
    unique_items = _deduplicate(items)
    grouped: dict[str, list[NewsItem]] = defaultdict(list)
    for item in unique_items:
        grouped[item.related_symbol].append(item)

    clusters = [
        _cluster_for_symbol(symbol, grouped_items)
        for symbol, grouped_items in grouped.items()
    ]
    clusters.sort(key=lambda cluster: (cluster.item_count, cluster.confidence), reverse=True)
    return clusters[:max_clusters]


def _deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        key = item.url or _normalize_title(item.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _cluster_for_symbol(symbol: str, items: list[NewsItem]) -> NewsCluster:
    publishers = {item.publisher for item in items if item.publisher}
    headlines = [item.title for item in items[:3]]
    urls = [item.url for item in items[:3]]
    return NewsCluster(
        topic=_topic(items),
        related_assets=[symbol],
        representative_headlines=headlines,
        source_urls=urls,
        item_count=len(items),
        confidence=_confidence(len(items), len(publishers)),
    )


def _topic(items: list[NewsItem]) -> str:
    counts: Counter[str] = Counter()
    for item in items:
        counts.update(_keywords(item.title))
    common = [word for word, _ in counts.most_common(4)]
    return " ".join(common) if common else "general news"


def _keywords(title: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]+", title.lower())
    return [word for word in words if word not in STOPWORDS and len(word) > 2]


def _normalize_title(title: str) -> str:
    return " ".join(_keywords(title))


def _confidence(item_count: int, publisher_count: int) -> float:
    return min(1.0, 0.35 + item_count * 0.15 + publisher_count * 0.15)
