# Source Run Health Design

## Goal

Add a generic source-run health layer so reports can distinguish real quiet markets from missing, failed, partial, or stale data collection.

## Scope

This first pass covers existing collection paths only:

- CSV price import.
- yfinance price collection.
- Google News RSS collection.

It does not add new data providers, scheduling, retries, macro APIs, SEC filing collection, or alert delivery.

## Problem

Current Data Coverage mostly inspects stored row counts. That is useful but incomplete:

- If Google RSS times out and old news rows remain, news may still look available.
- If yfinance partially fails, report sections may silently use incomplete market data.
- If no collection was attempted, the report cannot distinguish that from a valid no-data result.
- If collection succeeded days ago but has not refreshed, the report does not show staleness.

The report contract needs a source-level trust layer before expanding more data sources.

## Design

Add a reusable `SourceRun` record for every collection command.

Fields:

```text
source: csv_import | yfinance | google_news_rss
data_type: prices | news
status: success | partial_success | failed
attempted_at: ISO timestamp
completed_at: ISO timestamp
requested_symbols: list[str]
succeeded_symbols: list[str]
failed_symbols: list[str]
failure_reasons: dict[str, str]
row_count: int
latest_observed_at: ISO timestamp or null
```

Status rules:

```text
success = no failed symbols and row_count > 0
partial_success = at least one succeeded symbol and at least one failed symbol
failed = no succeeded symbols or row_count == 0 when a live collection was requested
```

CSV import is treated as `success` when rows are imported. It has no failed symbols unless the command itself raises before recording.

## Storage

Add a `source_runs` SQLite table. JSON fields are stored as text because SQLite is already the local storage layer and this project does not need a heavier schema yet.

The repository should provide:

```text
insert_run(run)
get_latest_run(data_type=None, source=None)
get_recent_runs(limit=20)
```

## Data Flow

```text
collect command
  -> run collector/importer
  -> persist data rows
  -> insert SourceRun
  -> daily report loads latest runs
  -> Data Coverage combines row counts + source health
  -> report renders source health rows and impacts
```

## Data Coverage Integration

Extend `analyze_data_coverage(...)` with optional source-run input.

Current row-count diagnostics remain. New source-health rows are additive:

```markdown
| Category | Item | Status | Rows | Latest | Detail |
|---|---|---|---:|---|---|
| Source Health | prices:yfinance | partial_success | 120 | 2026-07-07 | Failed: QQQ: YFRateLimitError |
| Source Health | news:google_news_rss | failed | 0 | N/A | Latest attempt failed: SPY timed out |
```

Impact examples:

```text
Price source yfinance partially succeeded; affected symbols may be stale or missing.
News source google_news_rss failed; Sections 5-6 may be empty or stale.
News source google_news_rss is stale; latest observed item is older than 2 days.
```

Freshness thresholds for the first pass:

```text
prices: stale if latest_observed_at is older than 3 calendar days
news: stale if latest_observed_at is older than 2 calendar days
```

These thresholds are intentionally conservative and can later move to config.

## Report Behavior

The daily report should keep the same top-level section order. `## Data Coverage` becomes more useful but remains the single place where source health appears.

The report should not infer market meaning from failed sources. It should only state data trust impact.

## Error Handling

Collection commands should continue current behavior:

- Persist successful rows even when some symbols fail.
- Print failed symbols and reasons.
- Return command status `0` for handled partial failures.

New behavior:

- Persist a `SourceRun` even for handled full failures, such as a Google RSS timeout for all requested symbols.
- Do not persist a run if initialization fails before the collection attempt begins.

## Testing

Use tests without network calls:

- Repository tests for inserting and reading source runs.
- CLI tests that monkeypatch collectors and assert source-run persistence.
- Data coverage tests for success, partial success, failed, stale, and missing source-run states.
- Markdown writer tests can reuse existing Data Coverage rendering because the row model does not need to change.

## Non-Goals

- Automatic retry/backoff.
- Provider failover.
- Scheduling.
- Provider-specific dashboards.
- New macro, SEC, or earnings sources.
- LLM interpretation of source health.
