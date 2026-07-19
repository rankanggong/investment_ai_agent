# Data Source Health Design

## Goal

Add a generic source health layer so the daily report can distinguish real quiet markets from missing, stale, partial, or failed data collection.

This closes the main gap between the report contract and the current implementation: `Data Coverage` currently knows row counts, but not collection attempts, source failures, or freshness.

## Scope

Implement a reusable collection-run record for existing sources:

- `csv_import` prices.
- `yfinance` prices.
- `google_news_rss` news.

Do not add new external sources in this phase. Do not add scheduler, macro APIs, SEC, earnings calendar, or LLM behavior.

## Data Model

Add a `SourceRun` model:

```text
source: csv_import | yfinance | google_news_rss
data_type: prices | news
status: success | partial_success | failed
attempted_at: datetime
completed_at: datetime
requested_symbols: list[str]
succeeded_symbols: list[str]
failed_symbols: list[str]
failure_reasons: dict[str, str]
row_count: int
latest_observed_at: str
```

Persist it in a new `source_runs` SQLite table. Store list/dict fields as JSON text to keep the schema simple and local.

## Status Rules

```text
success = no failed symbols and row_count > 0
partial_success = at least one succeeded symbol and at least one failed symbol
failed = no succeeded symbols or row_count == 0 when collection was expected to produce rows
```

CSV imports count as `success` when at least one row is imported. CSV does not have per-symbol failure detail in the current CLI, so `failed_symbols` is empty unless later validation is added.

## Data Flow

```text
collect command
  -> collector result
  -> upsert data rows
  -> insert SourceRun
  -> report daily reads latest source runs
  -> Data Coverage combines row counts + latest run state
  -> Markdown renders health/freshness impacts
```

## Report Behavior

`Data Coverage` should show source status in addition to row availability.

Examples:

```markdown
| Category | Item | Status | Rows | Latest | Detail |
|---|---|---|---:|---|---|
| News | google_news_rss | failed | 0 | N/A | Latest collection failed: SPY timed out. |
| Prices | yfinance | partial_success | 1480 | 2026-07-07 | Failed symbols: QQQ, GLD. |
```

Impact examples:

```text
Sections 5-6 may be empty or stale because google_news_rss failed on the latest run.
Market Overview may omit QQQ because yfinance failed for QQQ on the latest run.
```

## Freshness

First implementation should store `latest_observed_at`, but only use simple statuses:

```text
available
missing
insufficient
failed
partial_success
```

Do not overbuild freshness thresholds yet. Once source runs are persisted, a later phase can add `stale` rules per data type.

## Error Handling

Collection commands should continue to return `0` when they successfully handle collector failures, matching current behavior.

Failure details should be stored in `SourceRun.failure_reasons` and still printed to CLI output.

No tests should make live network calls.

## Testing

Add coverage for:

- Source run repository insert/read latest.
- CLI source-run persistence for yfinance success/partial failure.
- CLI source-run persistence for Google RSS failure.
- CSV import source-run persistence.
- Data coverage analyzer combining row-count gaps with source-run failures.
- Markdown rendering of enriched coverage rows and impacts.

## Non-Goals

- No scheduler.
- No retry policy changes.
- No new data providers.
- No formal macro data.
- No SEC or earnings calendar ingestion.
- No LLM summarization.

## Implementation Order

1. Add `SourceRun` model and repository.
2. Persist source runs from CLI collection commands.
3. Extend data coverage analyzer inputs and rules.
4. Update daily job to pass latest source runs into data coverage.
5. Update markdown tests if the rendered rows/impacts change.
