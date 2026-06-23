# Important News Clusters Design

## Goal

Add live Google News RSS collection and deterministic clustering to populate `## 5. Important News Clusters` in the daily report.

## Scope

This version uses watchlist-driven Google News RSS queries. It does not use Bedrock, paid APIs, embeddings, or article-body scraping. Tests mock RSS responses and avoid network calls.

## Architecture

Add `NewsItem` and `NewsCluster` dataclasses. A Google News RSS collector builds one query per watchlist symbol, fetches RSS XML, and normalizes title, link, publisher, published timestamp, source, and related symbol.

News items are stored in SQLite with a uniqueness constraint on normalized URL. A deterministic analyzer deduplicates items, groups them by related symbol, extracts simple title keywords, keeps representative headlines, and assigns confidence from item count and publisher diversity.

The daily report job reads recent stored news items, creates clusters, and passes them into the Markdown writer.

## CLI

Add:

```bash
python -m app.main collect news --google-rss
python -m app.main collect news --google-rss --symbols SPY QQQ
```

Default symbols come from `config/watchlist.yaml`.

## Error Handling

Each RSS query fails independently. Successful items are saved even if another symbol fails. Failures are reported with per-symbol reasons.

## Rendering

`## 5. Important News Clusters` renders:

- cluster topic
- related assets
- confidence
- representative headlines with publisher and URL

If no clusters are available, the report keeps a clear placeholder.

