# Data Source Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not commit during this plan unless the user explicitly asks; the current worktree contains pre-existing staged and unstaged changes.

**Goal:** Persist source collection attempts and surface source health in `Data Coverage` so reports can distinguish missing data from failed or partial collection.

**Architecture:** Add a reusable `SourceRun` model and repository backed by a new SQLite table. CLI collection commands record source runs after storing collected rows. The daily report reads latest source runs and passes them into the data coverage analyzer, which emits additional coverage rows and impact notes.

**Tech Stack:** Python dataclasses, sqlite3, JSON text fields, pytest, existing CLI/repository/report pipeline.

---

## File Structure

- Create: `app/models/source.py`
  - Owns the reusable `SourceRun` dataclass.
- Modify: `app/storage/schema.sql`
  - Adds `source_runs`.
- Create: `app/storage/repositories/source_run_repo.py`
  - Inserts source runs and reads latest source runs.
- Create: `tests/test_source_run_repository.py`
  - Covers persistence and latest-run lookup.
- Modify: `app/main.py`
  - Records source runs for CSV, yfinance, and Google RSS collection.
- Modify: `tests/test_cli.py`
  - Verifies source-run persistence from collection commands.
- Modify: `app/analyzers/data_coverage_analyzer.py`
  - Accepts latest source runs and adds source health rows/impacts.
- Modify: `app/jobs/daily_market_job.py`
  - Passes latest source runs to data coverage.
- Modify: `tests/test_data_coverage_analyzer.py`
  - Covers failed and partial source health rows/impacts.
- Modify: `tests/test_markdown_writer.py`
  - Add or adjust assertions only if rendered output changes beyond existing generic table behavior.

---

### Task 1: SourceRun Model And Repository

**Files:**
- Create: `app/models/source.py`
- Modify: `app/storage/schema.sql`
- Create: `app/storage/repositories/source_run_repo.py`
- Create: `tests/test_source_run_repository.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/test_source_run_repository.py`:

```python
from datetime import datetime, timezone

from app.models.source import SourceRun
from app.storage.db import initialize_database
from app.storage.repositories.source_run_repo import SourceRunRepository


def run(
    source: str,
    status: str,
    attempted_at: datetime,
    completed_at: datetime,
    row_count: int = 0,
) -> SourceRun:
    return SourceRun(
        source=source,
        data_type="prices",
        status=status,
        attempted_at=attempted_at,
        completed_at=completed_at,
        requested_symbols=["SPY", "QQQ"],
        succeeded_symbols=["SPY"] if status != "failed" else [],
        failed_symbols=["QQQ"] if status != "success" else [],
        failure_reasons={"QQQ": "Timeout"} if status != "success" else {},
        row_count=row_count,
        latest_observed_at="2026-07-07" if row_count else "",
    )


def test_source_run_repository_round_trips_json_fields(tmp_path):
    db_path = tmp_path / "finance.db"
    initialize_database(db_path)
    repo = SourceRunRepository(db_path)
    attempted_at = datetime(2026, 7, 8, 1, 2, 3, tzinfo=timezone.utc)
    completed_at = datetime(2026, 7, 8, 1, 2, 5, tzinfo=timezone.utc)

    repo.insert_run(
        run(
            source="yfinance",
            status="partial_success",
            attempted_at=attempted_at,
            completed_at=completed_at,
            row_count=10,
        )
    )

    latest = repo.get_latest_runs(["yfinance"])

    assert len(latest) == 1
    assert latest[0].source == "yfinance"
    assert latest[0].status == "partial_success"
    assert latest[0].requested_symbols == ["SPY", "QQQ"]
    assert latest[0].succeeded_symbols == ["SPY"]
    assert latest[0].failed_symbols == ["QQQ"]
    assert latest[0].failure_reasons == {"QQQ": "Timeout"}
    assert latest[0].row_count == 10
    assert latest[0].latest_observed_at == "2026-07-07"


def test_source_run_repository_returns_latest_per_source(tmp_path):
    db_path = tmp_path / "finance.db"
    initialize_database(db_path)
    repo = SourceRunRepository(db_path)

    repo.insert_run(
        run(
            source="yfinance",
            status="failed",
            attempted_at=datetime(2026, 7, 7, tzinfo=timezone.utc),
            completed_at=datetime(2026, 7, 7, 0, 1, tzinfo=timezone.utc),
        )
    )
    repo.insert_run(
        run(
            source="yfinance",
            status="success",
            attempted_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
            completed_at=datetime(2026, 7, 8, 0, 1, tzinfo=timezone.utc),
            row_count=20,
        )
    )
    repo.insert_run(
        SourceRun(
            source="google_news_rss",
            data_type="news",
            status="failed",
            attempted_at=datetime(2026, 7, 8, 2, tzinfo=timezone.utc),
            completed_at=datetime(2026, 7, 8, 2, 1, tzinfo=timezone.utc),
            requested_symbols=["SPY"],
            succeeded_symbols=[],
            failed_symbols=["SPY"],
            failure_reasons={"SPY": "URLError: timed out"},
            row_count=0,
            latest_observed_at="",
        )
    )

    latest = repo.get_latest_runs(["yfinance", "google_news_rss"])

    assert [(item.source, item.status) for item in latest] == [
        ("google_news_rss", "failed"),
        ("yfinance", "success"),
    ]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_source_run_repository.py -v`

Expected: FAIL with `ModuleNotFoundError` for `app.models.source` or repository import.

- [ ] **Step 3: Add `SourceRun` model**

Create `app/models/source.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SourceRun:
    source: str
    data_type: str
    status: str
    attempted_at: datetime
    completed_at: datetime
    requested_symbols: list[str]
    succeeded_symbols: list[str]
    failed_symbols: list[str]
    failure_reasons: dict[str, str] = field(default_factory=dict)
    row_count: int = 0
    latest_observed_at: str = ""
```

- [ ] **Step 4: Add schema table**

Append to `app/storage/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS source_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  data_type TEXT NOT NULL,
  status TEXT NOT NULL,
  attempted_at TEXT NOT NULL,
  completed_at TEXT NOT NULL,
  requested_symbols TEXT NOT NULL,
  succeeded_symbols TEXT NOT NULL,
  failed_symbols TEXT NOT NULL,
  failure_reasons TEXT NOT NULL,
  row_count INTEGER NOT NULL,
  latest_observed_at TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 5: Add repository**

Create `app/storage/repositories/source_run_repo.py`:

```python
import json
from datetime import datetime
from pathlib import Path

from app.models.source import SourceRun
from app.storage.db import connect


class SourceRunRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def insert_run(self, run: SourceRun) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO source_runs (
                  source, data_type, status, attempted_at, completed_at,
                  requested_symbols, succeeded_symbols, failed_symbols,
                  failure_reasons, row_count, latest_observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.source,
                    run.data_type,
                    run.status,
                    run.attempted_at.isoformat(),
                    run.completed_at.isoformat(),
                    json.dumps(run.requested_symbols),
                    json.dumps(run.succeeded_symbols),
                    json.dumps(run.failed_symbols),
                    json.dumps(run.failure_reasons),
                    run.row_count,
                    run.latest_observed_at,
                ),
            )

    def get_latest_runs(self, sources: list[str]) -> list[SourceRun]:
        if not sources:
            return []
        placeholders = ",".join("?" for _ in sources)
        with connect(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT source, data_type, status, attempted_at, completed_at,
                       requested_symbols, succeeded_symbols, failed_symbols,
                       failure_reasons, row_count, latest_observed_at
                FROM source_runs
                WHERE id IN (
                  SELECT MAX(id)
                  FROM source_runs
                  WHERE source IN ({placeholders})
                  GROUP BY source
                )
                ORDER BY completed_at DESC, source ASC
                """,
                tuple(sources),
            ).fetchall()
        return [_row_to_source_run(row) for row in rows]


def _row_to_source_run(row) -> SourceRun:
    return SourceRun(
        source=row["source"],
        data_type=row["data_type"],
        status=row["status"],
        attempted_at=datetime.fromisoformat(row["attempted_at"]),
        completed_at=datetime.fromisoformat(row["completed_at"]),
        requested_symbols=json.loads(row["requested_symbols"]),
        succeeded_symbols=json.loads(row["succeeded_symbols"]),
        failed_symbols=json.loads(row["failed_symbols"]),
        failure_reasons=json.loads(row["failure_reasons"]),
        row_count=row["row_count"],
        latest_observed_at=row["latest_observed_at"] or "",
    )
```

- [ ] **Step 6: Run repository tests**

Run: `python -m pytest tests/test_source_run_repository.py -v`

Expected: PASS.

---

### Task 2: Persist Source Runs From CLI Collection

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add CLI source-run tests**

Append imports in `tests/test_cli.py`:

```python
from app.storage.repositories.source_run_repo import SourceRunRepository
```

Add tests:

```python
def test_yfinance_collection_records_source_run(tmp_path, monkeypatch):
    db_path = tmp_path / "finance.db"

    def collect(symbols):
        return YFinanceCollectionResult(
            bars=[
                PriceBar(
                    symbol="SPY",
                    date=date(2026, 7, 7),
                    open=100,
                    high=101,
                    low=99,
                    close=100,
                    adjusted_close=100,
                    volume=1000,
                    source="yfinance",
                )
            ],
            failed_symbols=["QQQ"],
            failure_reasons={"QQQ": "Timeout"},
        )

    monkeypatch.setattr(app.main, "collect_yfinance_prices", collect)

    app.main.main(
        [
            "collect",
            "prices",
            "--yfinance",
            "--symbols",
            "spy",
            "qqq",
            "--db",
            str(db_path),
        ]
    )

    runs = SourceRunRepository(db_path).get_latest_runs(["yfinance"])

    assert len(runs) == 1
    assert runs[0].source == "yfinance"
    assert runs[0].data_type == "prices"
    assert runs[0].status == "partial_success"
    assert runs[0].requested_symbols == ["SPY", "QQQ"]
    assert runs[0].succeeded_symbols == ["SPY"]
    assert runs[0].failed_symbols == ["QQQ"]
    assert runs[0].failure_reasons == {"QQQ": "Timeout"}
    assert runs[0].row_count == 1
    assert runs[0].latest_observed_at == "2026-07-07"


def test_google_news_collection_records_failed_source_run(tmp_path, monkeypatch):
    db_path = tmp_path / "finance.db"

    def collect(symbols):
        return NewsCollectionResult(
            items=[],
            failed_symbols=["SPY"],
            failure_reasons={"SPY": "URLError: timed out"},
        )

    monkeypatch.setattr(app.main, "collect_google_news", collect)

    app.main.main(
        [
            "collect",
            "news",
            "--google-rss",
            "--symbols",
            "spy",
            "--db",
            str(db_path),
        ]
    )

    runs = SourceRunRepository(db_path).get_latest_runs(["google_news_rss"])

    assert len(runs) == 1
    assert runs[0].source == "google_news_rss"
    assert runs[0].data_type == "news"
    assert runs[0].status == "failed"
    assert runs[0].requested_symbols == ["SPY"]
    assert runs[0].succeeded_symbols == []
    assert runs[0].failed_symbols == ["SPY"]
    assert runs[0].failure_reasons == {"SPY": "URLError: timed out"}
    assert runs[0].row_count == 0
    assert runs[0].latest_observed_at == ""
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_cli.py::test_yfinance_collection_records_source_run tests/test_cli.py::test_google_news_collection_records_failed_source_run -v`

Expected: FAIL because CLI does not write source runs yet.

- [ ] **Step 3: Add helper imports**

In `app/main.py`, add:

```python
from datetime import datetime, timezone

from app.models.source import SourceRun
from app.storage.repositories.source_run_repo import SourceRunRepository
```

- [ ] **Step 4: Add helper functions near the bottom of `app/main.py`**

```python
def _source_run_status(
    row_count: int,
    requested_symbols: list[str],
    failed_symbols: list[str],
) -> str:
    succeeded_count = len(set(requested_symbols) - set(failed_symbols))
    if row_count > 0 and not failed_symbols:
        return "success"
    if row_count > 0 and succeeded_count > 0 and failed_symbols:
        return "partial_success"
    return "failed"


def _latest_price_date(bars: list[PriceBar]) -> str:
    if not bars:
        return ""
    return max(bar.date for bar in bars).isoformat()


def _latest_news_date(items: list[NewsItem]) -> str:
    dates = [item.published_at for item in items if item.published_at is not None]
    if not dates:
        return ""
    return max(dates).isoformat()


def _succeeded_symbols(
    requested_symbols: list[str],
    failed_symbols: list[str],
) -> list[str]:
    failed = set(failed_symbols)
    return [symbol for symbol in requested_symbols if symbol not in failed]
```

- [ ] **Step 5: Record yfinance and CSV source runs**

In the prices collection branch, set `attempted_at = datetime.now(timezone.utc)` before collection/import starts and `completed_at = datetime.now(timezone.utc)` after `PriceRepository(args.db).upsert_many(bars)`.

After upserting prices, add:

```python
        source = "csv_import" if args.csv else "yfinance"
        requested_symbols = (
            sorted({bar.symbol for bar in bars})
            if args.csv
            else symbols
        )
        SourceRunRepository(args.db).insert_run(
            SourceRun(
                source=source,
                data_type="prices",
                status=_source_run_status(
                    len(bars),
                    requested_symbols,
                    failed_symbols,
                ),
                attempted_at=attempted_at,
                completed_at=completed_at,
                requested_symbols=requested_symbols,
                succeeded_symbols=_succeeded_symbols(
                    requested_symbols,
                    failed_symbols,
                ),
                failed_symbols=failed_symbols,
                failure_reasons=failure_reasons,
                row_count=len(bars),
                latest_observed_at=_latest_price_date(bars),
            )
        )
```

- [ ] **Step 6: Record Google RSS source runs**

In the news branch, set `attempted_at = datetime.now(timezone.utc)` before `collection = collect_google_news(symbols)` and `completed_at = datetime.now(timezone.utc)` after `NewsRepository(args.db).upsert_many(collection.items)`.

After upserting news, add:

```python
        SourceRunRepository(args.db).insert_run(
            SourceRun(
                source="google_news_rss",
                data_type="news",
                status=_source_run_status(
                    len(collection.items),
                    symbols,
                    collection.failed_symbols,
                ),
                attempted_at=attempted_at,
                completed_at=completed_at,
                requested_symbols=symbols,
                succeeded_symbols=_succeeded_symbols(
                    symbols,
                    collection.failed_symbols,
                ),
                failed_symbols=collection.failed_symbols,
                failure_reasons=collection.failure_reasons,
                row_count=len(collection.items),
                latest_observed_at=_latest_news_date(collection.items),
            )
        )
```

- [ ] **Step 7: Run CLI tests**

Run: `python -m pytest tests/test_cli.py -v`

Expected: PASS.

---

### Task 3: Extend Data Coverage With Source Health

**Files:**
- Modify: `app/analyzers/data_coverage_analyzer.py`
- Modify: `tests/test_data_coverage_analyzer.py`

- [ ] **Step 1: Add data coverage tests**

In `tests/test_data_coverage_analyzer.py`, import:

```python
from datetime import datetime, timezone

from app.models.source import SourceRun
```

Add helper:

```python
def source_run(
    source: str,
    data_type: str,
    status: str,
    row_count: int,
    latest_observed_at: str = "",
) -> SourceRun:
    return SourceRun(
        source=source,
        data_type=data_type,
        status=status,
        attempted_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
        completed_at=datetime(2026, 7, 8, 0, 1, tzinfo=timezone.utc),
        requested_symbols=["SPY", "QQQ"],
        succeeded_symbols=["SPY"] if status != "failed" else [],
        failed_symbols=["QQQ"] if status != "success" else [],
        failure_reasons={"QQQ": "Timeout"} if status != "success" else {},
        row_count=row_count,
        latest_observed_at=latest_observed_at,
    )
```

Add test:

```python
def test_data_coverage_includes_failed_and_partial_source_runs():
    result = analyze_data_coverage(
        price_history={},
        price_symbols=[],
        macro_symbols=[],
        popular_company_symbols=[],
        news_item_count=0,
        source_runs=[
            source_run("google_news_rss", "news", "failed", 0),
            source_run("yfinance", "prices", "partial_success", 10, "2026-07-07"),
        ],
    )

    google_row = _row(result, "Source", "news:google_news_rss")
    yfinance_row = _row(result, "Source", "prices:yfinance")

    assert google_row.status == "failed"
    assert google_row.rows == 0
    assert google_row.latest == "N/A"
    assert "Latest collection failed" in google_row.detail
    assert "QQQ: Timeout" in google_row.detail

    assert yfinance_row.status == "partial_success"
    assert yfinance_row.rows == 10
    assert yfinance_row.latest == "2026-07-07"
    assert "Failed symbols: QQQ" in yfinance_row.detail

    assert (
        "Sections 5-6 may be empty or stale because google_news_rss failed on the latest run."
        in result.impacts
    )
    assert (
        "Prices from yfinance are partially available; failed symbols: QQQ."
        in result.impacts
    )
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_data_coverage_analyzer.py::test_data_coverage_includes_failed_and_partial_source_runs -v`

Expected: FAIL because `analyze_data_coverage` does not accept `source_runs`.

- [ ] **Step 3: Extend analyzer signature and imports**

In `app/analyzers/data_coverage_analyzer.py`, add:

```python
from app.models.source import SourceRun
```

Change signature:

```python
def analyze_data_coverage(
    price_history: dict[str, list[PriceBar]],
    price_symbols: list[str],
    macro_symbols: list[str],
    popular_company_symbols: list[str],
    news_item_count: int,
    source_runs: list[SourceRun] | None = None,
) -> DataCoverage:
```

After `rows.append(_news_row(news_item_count))`, add:

```python
    rows.extend(_source_run_row(run) for run in (source_runs or []))
```

- [ ] **Step 4: Add source-row helpers**

Add:

```python
def _source_run_row(run: SourceRun) -> DataCoverageRow:
    latest = run.latest_observed_at or "N/A"
    return DataCoverageRow(
        category="Source",
        item=f"{run.data_type}:{run.source}",
        status=run.status,
        rows=run.row_count,
        latest=latest,
        detail=_source_run_detail(run),
    )


def _source_run_detail(run: SourceRun) -> str:
    if run.status == "success":
        return f"Latest collection succeeded for {len(run.succeeded_symbols)} symbols."
    if run.status == "partial_success":
        return "Failed symbols: " + _join_items(run.failed_symbols)
    if run.failure_reasons:
        failures = "; ".join(
            f"{symbol}: {reason}"
            for symbol, reason in sorted(run.failure_reasons.items())
        )
        return f"Latest collection failed: {failures}"
    return "Latest collection failed."
```

- [ ] **Step 5: Add source impacts**

At the end of `_impacts(rows)`, before `if not impacts`, add:

```python
    for row in rows:
        if row.category != "Source":
            continue
        if row.status == "failed" and row.item == "news:google_news_rss":
            impacts.append(
                "Sections 5-6 may be empty or stale because google_news_rss failed on the latest run."
            )
        elif row.status == "partial_success" and row.item.startswith("prices:"):
            impacts.append(
                f"Prices from {row.item.split(':', 1)[1]} are partially available; "
                f"failed symbols: {_failed_symbols_from_detail(row.detail)}."
            )
```

Add helper:

```python
def _failed_symbols_from_detail(detail: str) -> str:
    prefix = "Failed symbols: "
    if detail.startswith(prefix):
        return detail[len(prefix):]
    return "unknown"
```

- [ ] **Step 6: Run analyzer tests**

Run: `python -m pytest tests/test_data_coverage_analyzer.py -v`

Expected: PASS.

---

### Task 4: Wire Latest Source Runs Into Daily Report

**Files:**
- Modify: `app/jobs/daily_market_job.py`
- Test: focused existing tests.

- [ ] **Step 1: Add repository import**

In `app/jobs/daily_market_job.py`, add:

```python
from app.storage.repositories.source_run_repo import SourceRunRepository
```

- [ ] **Step 2: Read source runs before data coverage**

After `recent_news = NewsRepository(db_path).get_recent_items()`, add:

```python
    source_runs = SourceRunRepository(db_path).get_latest_runs(
        ["csv_import", "yfinance", "google_news_rss"]
    )
```

- [ ] **Step 3: Pass source runs to data coverage**

In `analyze_data_coverage(...)`, add:

```python
        source_runs=source_runs,
```

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_data_coverage_analyzer.py tests/test_markdown_writer.py -v`

Expected: PASS.

---

### Task 5: Full Verification

**Files:**
- No edits.

- [ ] **Step 1: Run full suite**

Run: `python -m pytest -v`

Expected: PASS.

- [ ] **Step 2: Inspect status**

Run: `git status --short`

Expected: source health files appear alongside existing dirty worktree changes. Do not revert unrelated files.

---

## Design Notes

This plan intentionally stores source health at the collection-command boundary rather than inside individual collectors. That keeps collectors focused on fetching/parsing and lets future macro, SEC, and earnings collectors reuse the same `SourceRunRepository`.

The first implementation stores `latest_observed_at` but does not implement age-based stale thresholds. Staleness rules should be added later per data type after source-run history exists.

## Self-Review

Spec coverage:

- Generic source run model and table: Task 1.
- CLI persistence for CSV, yfinance, and Google RSS: Task 2.
- Data coverage integration: Task 3.
- Daily report integration: Task 4.
- Verification: Task 5.

Placeholder scan:

- No placeholder markers or undefined task references remain.

Type consistency:

- `SourceRun`, `SourceRunRepository`, and `source_runs` names are consistent across tasks.
