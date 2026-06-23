from datetime import datetime, timezone

from app.collectors.google_news_collector import collect_google_news


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss>
  <channel>
    <item>
      <title>SPY rises as Fed rate hopes lift stocks - Reuters</title>
      <link>https://news.google.com/rss/articles/abc?utm_source=x</link>
      <source url="https://www.reuters.com">Reuters</source>
      <pubDate>Mon, 22 Jun 2026 03:15:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_collect_google_news_normalizes_rss_items():
    calls = []

    def fetcher(query):
        calls.append(query)
        return RSS

    result = collect_google_news(["spy"], fetcher=fetcher)

    assert calls == ["SPY"]
    assert result.failed_symbols == []
    assert len(result.items) == 1
    item = result.items[0]
    assert item.title == "SPY rises as Fed rate hopes lift stocks - Reuters"
    assert item.url == "https://news.google.com/rss/articles/abc"
    assert item.publisher == "Reuters"
    assert item.related_symbol == "SPY"
    assert item.source == "google_news_rss"
    assert item.published_at == datetime(2026, 6, 22, 3, 15, tzinfo=timezone.utc)


def test_collect_google_news_continues_after_symbol_fetch_failure():
    def fetcher(query):
        if query == "BAD":
            raise RuntimeError("rss unavailable")
        return RSS

    result = collect_google_news(["BAD", "QQQ"], fetcher=fetcher)

    assert [item.related_symbol for item in result.items] == ["QQQ"]
    assert result.failed_symbols == ["BAD"]
    assert result.failure_reasons == {"BAD": "RuntimeError: rss unavailable"}
