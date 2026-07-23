from datetime import datetime, timezone

from app.analyzers.fundamental_event_analyzer import analyze_fundamental_events
from app.models.analysis import CompanyEvent, NewsItem


def item(title, symbol="AAPL", publisher="Reuters", url="https://example.com/a"):
    return NewsItem(
        title=title,
        url=url,
        publisher=publisher,
        published_at=datetime(2026, 6, 25, 3, 15, tzinfo=timezone.utc),
        related_symbol=symbol,
        source="google_news_rss",
        entity_kind="etf" if symbol == "SPY" else "company",
        entity_confidence=0.95,
        entity_match_reason="test fixture",
    )


def test_fundamental_event_analyzer_detects_event_headlines():
    events = analyze_fundamental_events(
        [
            item(
                "Apple reports quarterly earnings and revenue beat estimates",
                "AAPL",
                url="https://example.com/a",
            ),
            item(
                "Microsoft raises forecast after strong cloud demand",
                "MSFT",
                "Bloomberg",
                "https://example.com/b",
            ),
            item(
                "Nvidia faces antitrust probe from regulator",
                "NVDA",
                "Reuters",
                "https://example.com/c",
            ),
            item("SPY rises as Fed hopes lift market", "SPY", "Reuters", "https://example.com/d"),
        ]
    )

    assert [event.event_type for event in events] == [
        "earnings_release",
        "guidance_change",
        "regulatory_event",
    ]
    assert events[0].related_symbol == "AAPL"
    assert events[0].headline == "Apple reports quarterly earnings and revenue beat estimates"
    assert events[0].publisher == "Reuters"
    assert events[0].source_url == "https://example.com/a"
    assert events[0].confidence > 0.5
    assert all(isinstance(event, CompanyEvent) for event in events)
    assert events[0].review_type == "company_event_review"
    assert events[0].article_count == 1
    assert events[1].review_type == "company_event_review"
    assert events[2].review_type == "company_event_review"
