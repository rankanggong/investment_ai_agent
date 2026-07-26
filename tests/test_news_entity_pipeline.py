from datetime import datetime, timezone

from app.analyzers.asset_event_analyzer import analyze_asset_events
from app.analyzers.news_entity_linker import link_news_entities
from app.analyzers.news_cluster_analyzer import analyze_news_clusters
from app.models.analysis import (
    AssetEntity,
    CommodityEvent,
    CompanyEvent,
    EtfEvent,
    IndexEvent,
    NewsItem,
)


NOW = datetime(2026, 7, 19, 8, 0, tzinfo=timezone.utc)


def item(title: str, query_symbol: str, url: str) -> NewsItem:
    return NewsItem(
        title=title,
        url=url,
        publisher="Example",
        published_at=NOW,
        related_symbol=query_symbol,
        source="google_news_rss",
        query_symbol=query_symbol,
    )


def test_entity_linker_rejects_ordinary_word_spy_and_fails_closed():
    result = link_news_entities(
        items=[
            item("SPY falls as semiconductor shares retreat", "SPY", "https://example.com/market"),
            item("New spy film has a strong opening weekend", "SPY", "https://example.com/film"),
            item("Why GPIQ lags QQQ in rallies", "QQQ", "https://example.com/qqq"),
        ],
        entities=[
            AssetEntity("SPY", "SPDR S&P 500 ETF Trust", "etf", ["S&P 500 ETF"]),
            AssetEntity("QQQ", "Invesco QQQ Trust", "etf", ["Nasdaq 100 ETF"]),
        ],
        precision_threshold=0.80,
    )

    assert [news.url for news in result.linked_items] == [
        "https://example.com/market",
        "https://example.com/qqq",
    ]
    assert [news.url for news in result.rejected_items] == ["https://example.com/film"]
    assert result.gate.entity_precision == 2 / 3
    assert result.gate.status == "data_quality_review"
    assert result.gate.news_score is None
    assert result.gate.fundamental_score is None
    assert result.gate.portfolio_action == "unavailable"
    clusters = analyze_news_clusters(result.linked_items + result.rejected_items)
    assert all("film" not in headline.casefold() for cluster in clusters for headline in cluster.representative_headlines)


def test_symbol_only_entity_name_does_not_bypass_ambiguous_ticker_check():
    result = link_news_entities(
        [item("A new spy film opens", "SPY", "https://example.com/film")],
        [AssetEntity("SPY", "SPY", "etf")],
    )

    assert result.linked_items == []
    assert result.rejected_items[0].entity_confidence == 0.20


def test_asset_types_use_distinct_event_schemas_and_etf_dividend_noise_is_ignored():
    linked = link_news_entities(
        items=[
            item("Apple reports quarterly earnings", "AAPL", "https://example.com/apple"),
            item("SPY announces an expense ratio fee cut", "SPY", "https://example.com/spy"),
            item("S&P 500 adds Acme in constituent change", "SPX", "https://example.com/spx"),
            item("Gold supply disruption deepens", "GOLD", "https://example.com/gold"),
            item("Why GPIQ lags QQQ, yet retirees like its monthly dividend", "QQQ", "https://example.com/gpiq"),
        ],
        entities=[
            AssetEntity("AAPL", "Apple", "company", ["Apple Inc"]),
            AssetEntity("SPY", "SPDR S&P 500 ETF Trust", "etf", ["S&P 500 ETF"]),
            AssetEntity("SPX", "S&P 500", "index", ["S&P 500 Index"]),
            AssetEntity("GOLD", "Gold", "commodity", ["gold bullion"]),
            AssetEntity("QQQ", "Invesco QQQ Trust", "etf", []),
        ],
        precision_threshold=0.50,
    )

    events = analyze_asset_events(linked.linked_items)

    assert [type(event) for event in events] == [
        CompanyEvent,
        EtfEvent,
        IndexEvent,
        CommodityEvent,
    ]
    assert [event.event_type for event in events] == [
        "earnings_release",
        "fee_change",
        "constituent_change",
        "supply_disruption",
    ]
    assert all(event.related_symbol != "QQQ" for event in events)


def test_multiple_articles_about_one_event_are_counted_once():
    linked = link_news_entities(
        items=[
            item("Apple reports quarterly earnings", "AAPL", "https://example.com/a"),
            item("AAPL quarterly earnings results beat estimates", "AAPL", "https://example.com/b"),
        ],
        entities=[AssetEntity("AAPL", "Apple", "company", ["Apple Inc"])],
    )

    events = analyze_asset_events(linked.linked_items)

    assert linked.gate.status == "available"
    assert linked.gate.portfolio_action == "unavailable"
    assert linked.gate.news_score is None
    assert len(events) == 1
    assert isinstance(events[0], CompanyEvent)
    assert events[0].event_type == "earnings_release"
    assert events[0].article_count == 2
    assert events[0].source_urls == ["https://example.com/a", "https://example.com/b"]
