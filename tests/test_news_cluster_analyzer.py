from datetime import datetime, timezone

from app.analyzers.news_cluster_analyzer import analyze_news_clusters
from app.models.analysis import NewsItem


def item(title, url, symbol, publisher):
    return NewsItem(
        title=title,
        url=url,
        publisher=publisher,
        published_at=datetime(2026, 6, 22, 3, 15, tzinfo=timezone.utc),
        related_symbol=symbol,
        source="google_news_rss",
    )


def test_news_cluster_analyzer_deduplicates_and_groups_by_symbol():
    clusters = analyze_news_clusters(
        [
            item("SPY rallies as Fed rate hopes lift market", "https://example.com/a", "SPY", "Reuters"),
            item("SPY rallies as Fed rate hopes lift market", "https://example.com/a", "SPY", "Reuters"),
            item("SPY gains as Fed hopes support stocks", "https://example.com/b", "SPY", "Bloomberg"),
            item("Gold rises as dollar weakens", "https://example.com/c", "GLD", "Reuters"),
        ]
    )

    assert len(clusters) == 2
    spy = clusters[0]
    assert spy.related_assets == ["SPY"]
    assert spy.item_count == 2
    assert spy.confidence > 0.5
    assert "fed" in spy.topic
    assert spy.representative_headlines == [
        "SPY rallies as Fed rate hopes lift market",
        "SPY gains as Fed hopes support stocks",
    ]
    assert spy.source_count == 2
    assert spy.why_it_matters == (
        "2 stored headlines from 2 sources mention SPY, so this cluster may explain asset-specific attention."
    )
    assert spy.manual_read_urls == ["https://example.com/a", "https://example.com/b"]
