from datetime import datetime, timezone

from app.models.analysis import NewsItem
from app.storage.db import initialize_database
from app.storage.repositories.news_repo import NewsRepository


def make_item(title, url, symbol="SPY"):
    return NewsItem(
        title=title,
        url=url,
        publisher="Reuters",
        published_at=datetime(2026, 6, 22, 3, 15, tzinfo=timezone.utc),
        related_symbol=symbol,
        source="google_news_rss",
    )


def test_news_repository_upserts_by_url_and_reads_recent_items(tmp_path):
    db_path = tmp_path / "finance.db"
    initialize_database(db_path)
    repo = NewsRepository(db_path)

    repo.upsert_many(
        [
            make_item("First title", "https://example.com/a", "SPY"),
            make_item("QQQ title", "https://example.com/b", "QQQ"),
        ]
    )
    repo.upsert_many([make_item("Updated title", "https://example.com/a", "SPY")])

    items = repo.get_recent_items(limit=10)
    by_url = {item.url: item for item in items}

    assert len(items) == 2
    assert by_url["https://example.com/a"].title == "Updated title"
    assert by_url["https://example.com/a"].related_symbol == "SPY"
