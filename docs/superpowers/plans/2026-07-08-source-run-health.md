# Source Run Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist collection attempt health for existing price/news sources and surface it in Data Coverage.

**Architecture:** Add a generic `SourceRun` dataclass, a `source_runs` SQLite table, and a repository. CLI collection commands record source runs after persisting collected rows. Data Coverage accepts recent source runs and adds source-health rows and impacts without changing the existing report section order.

**Tech Stack:** Python dataclasses, SQLite, stdlib `json`, pytest, existing CLI/repository/analyzer patterns.

---

## File Structure

- Create: `app/models/source_run.py`
  - Owns `SourceRun` and status derivation helper.
- Modify: `app/storage/schema.sql`
  - Adds `source_runs` table.
- Create: `app/storage/repositories/source_run_repo.py`
  - Inserts and reads source-run records.
- Modify: `app/main.py`
  - Records source runs for CSV price import, yfinance price collection, and Google News RSS collection.
- Modify: `app/analyzers/data_coverage_analyzer.py`
  - Accepts optional source runs, adds Source Health rows and impacts.
- Modify: `app/jobs/daily_market_job.py`
  - Loads recent source runs and passes them into Data Coverage.
- Create: `tests/test_source_run_repository.py`
  - Covers source-run persistence and JSON roundtrip.
- Modify: `tests/test_cli.py`
  - Covers source-run recording for yfinance, CSV, and Google RSS.
- Modify: `tests/test_data_coverage_analyzer.py`
  - Covers source-health rows, partial failure impacts, failed source impacts, and staleness.

---

### Task 1: SourceRun Model And Repository

**Files:**
- Create: `app/models/source_run.py`
- Modify: `app/storage/schema.sql`
- Create: `app/storage/repositories/source_run_repo.py`
- Create: `tests/test_source_run_repository.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/test_source_run_repository.py`:

```python
from datetime import datetime, timezone

from app.models.source_run import SourceRun, derive_source_run_status
from app.storage.db import initialize_database
from app.storage.repositories.source_run_repo import SourceRunRepository


def test_source_run_repository_inserts_and_reads_latest_run(tmp_path):
    db_path = tmp_path / "finance.db"
    initialize_database(db_path)
    repo = SourceRunRepository(db_path)

    run = SourceRun(
        source="yfinance",
        data_type="prices",
        status="partial_success",
        attempted_at=datetime(2026, 7, 8, 1, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 7, 8, 1, 1, tzinfo=timezone.utc),
        requested_symbols=["SPY", "QQQ"],
        succeeded_symbols=["SPY"],
        failed_symbols=["QQQ"],
        failure_reasons={"QQQ": "YFRateLimitError: Too Many Requests"},
        row_count=120,
        latest_observed_at=datetime(2026, 7, 7, 0, 0, tzinfo=timezone.utc),
    )

    repo.insert_run(run)

    latest = repo.get_latest_run(data_type="prices", source="yfinance")

    assert latest == run


def test_source_run_repository_reads_recent_runs_in_descending_attempt_order(tmp_path):
    db_path = tmp_path / "finance.db"
    initialize_database(db_path)
    repo = SourceRunRepository(db_path)

    older = SourceRun(
        source="google_news_rss",
        data_type="news",
        status="failed",
        attempted_at=datetime(2026, 7, 7, 1, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 7, 7, 1, 1, tzinfo=timezone.utc),
        requested_symbols=["SPY"],
        succeeded_symbols=[],
        failed_symbols=["SPY"],
        failure_reasons={"SPY": "URLError: timed out"},
        row_count=0,
        latest_observed_at=None,
    )
    newer = SourceRun(
        source="google_news_rss",
        data_type="news",
        status="success",
        attempted_at=datetime(2026, 7, 8, 1, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 7, 8, 1, 1, tzinfo=timezone.utc),
        requested_symbols=["SPY"],
        succeeded_symbols=["SPY"],
        failed_symbols=[],
        failure_reasons={},
        row_count=3,
        latest_observed_at=datetime(2026, 7, 8, 0, 30, tzinfo=timezone.utc),
    )

    repo.insert_run(older)
    repo.insert_run(newer)

    recent = repo.get_recent_runs(limit=2)

    assert recent == [newer, older]


def test_derive_source_run_status():
    assert derive_source_run_status(row_count=10, succeeded_symbols=["SPY"], failed_symbols=[]) == "success"
    assert derive_source_run_status(row_count=10, succeeded_symbols=["SPY"], failed_symbols=["QQQ"]) == "partial_success"
    assert derive_source_run_status(row_count=0, succeeded_symbols=[], failed_symbols=["SPY"]) == "failed"
```

- [ ] **Step 2: Run tests to verify missing module failure**

Run: `python -m pytest tests/test_source_run_repository.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.source_run'`.

- [ ] **Step 3: Add model**

Create `app/models/source_run.py`:

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
    latest_observed_at: datetime | None = None


def derive_source_run_status(
    row_count: int,
    succeeded_symbols: list[str],
    failed_symbols: list[str],
) -> str:
    if succeeded_symbols and failed_symbols:
        return "partial_success"
    if succeeded_symbols and row_count > 0:
        return "success"
    return "failed"
```

- [ ] **Step 4: Add table**

Append this table to `app/storage/schema.sql`:

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

from app.models.source_run import SourceRun
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
                    run.latest_observed_at.isoformat()
                    if run.latest_observed_at
                    else None,
                ),
            )

    def get_latest_run(
        self,
        data_type: str | None = None,
        source: str | None = None,
    ) -> SourceRun | None:
        clauses: list[str] = []
        params: list[str] = []
        if data_type is not None:
            clauses.append("data_type = ?")
            params.append(data_type)
        if source is not None:
            clauses.append("source = ?")
            params.append(source)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect(self.db_path) as conn:
            row = conn.execute(
                f"""
                SELECT source, data_type, status, attempted_at, completed_at,
                       requested_symbols, succeeded_symbols, failed_symbols,
                       failure_reasons, row_count, latest_observed_at
                FROM source_runs
                {where}
                ORDER BY attempted_at DESC, id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
        return _row_to_source_run(row) if row else None

    def get_recent_runs(self, limit: int = 20) -> list[SourceRun]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT source, data_type, status, attempted_at, completed_at,
                       requested_symbols, succeeded_symbols, failed_symbols,
                       failure_reasons, row_count, latest_observed_at
                FROM source_runs
                ORDER BY attempted_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
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
        latest_observed_at=(
            datetime.fromisoformat(row["latest_observed_at"])
            if row["latest_observed_at"]
            else None
        ),
    )
```

- [ ] **Step 6: Run repository tests**

Run: `python -m pytest tests/test_source_run_repository.py -v`

Expected: PASS.

---

### Task 2: Record Source Runs From CLI Collection Commands

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add CLI source-run tests**

Append imports to `tests/test_cli.py`:

```python
from app.storage.repositories.source_run_repo import SourceRunRepository
```

Extend `test_yfinance_collection_uses_watchlist_and_reports_failures` after existing output assertions:

```python
    source_run = SourceRunRepository(db_path).get_latest_run(
        data_type="prices",
        source="yfinance",
    )
    assert source_run is not None
    assert source_run.status == "partial_success"
    assert source_run.requested_symbols == ["SPY", "QQQ"]
    assert source_run.succeeded_symbols == ["SPY"]
    assert source_run.failed_symbols == ["QQQ"]
    assert source_run.failure_reasons == {"QQQ": "YFRateLimitError: Too Many Requests"}
    assert source_run.row_count == 1
    assert source_run.latest_observed_at is not None
    assert source_run.latest_observed_at.date() == date(2026, 6, 10)
```

Extend `test_google_news_collection_uses_watchlist_and_reports_failures` after existing output assertions:

```python
    source_run = SourceRunRepository(db_path).get_latest_run(
        data_type="news",
        source="google_news_rss",
    )
    assert source_run is not None
    assert source_run.status == "partial_success"
    assert source_run.requested_symbols == ["SPY", "QQQ"]
    assert source_run.succeeded_symbols == ["SPY"]
    assert source_run.failed_symbols == ["QQQ"]
    assert source_run.failure_reasons == {"QQQ": "RuntimeError: rss unavailable"}
    assert source_run.row_count == 1
    assert source_run.latest_observed_at is not None
    assert source_run.latest_observed_at == datetime(2026, 6, 22, 3, 15, tzinfo=timezone.utc)
```

Add a new CSV import test:

```python
def test_csv_price_import_records_source_run(tmp_path):
    csv_path = tmp_path / "prices.csv"
    csv_path.write_text(
        "symbol,date,open,high,low,close,adjusted_close,volume\n"
        "SPY,2026-06-10,100,102,99,101,101,1000\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "finance.db"

    result = app.main.main(
        [
            "collect",
            "prices",
            "--csv",
            str(csv_path),
            "--db",
            str(db_path),
        ]
    )

    assert result == 0
    source_run = SourceRunRepository(db_path).get_latest_run(
        data_type="prices",
        source="csv_import",
    )
    assert source_run is not None
    assert source_run.status == "success"
    assert source_run.requested_symbols == ["SPY"]
    assert source_run.succeeded_symbols == ["SPY"]
    assert source_run.failed_symbols == []
    assert source_run.row_count == 1
    assert source_run.latest_observed_at is not None
    assert source_run.latest_observed_at.date() == date(2026, 6, 10)
```

- [ ] **Step 2: Run CLI tests to verify failure**

Run: `python -m pytest tests/test_cli.py -v`

Expected: FAIL because `app.main` does not record source runs yet.

- [ ] **Step 3: Add CLI recording helpers**

In `app/main.py`, add imports:

```python
from datetime import datetime, timezone

from app.models.source_run import SourceRun, derive_source_run_status
from app.storage.repositories.source_run_repo import SourceRunRepository
```

Add helper functions near the bottom of `app/main.py`:

```python
def _record_source_run(
    db_path: Path,
    source: str,
    data_type: str,
    attempted_at: datetime,
    requested_symbols: list[str],
    row_symbols: list[str],
    failed_symbols: list[str],
    failure_reasons: dict[str, str],
    row_count: int,
    latest_observed_at: datetime | None,
) -> None:
    succeeded_symbols = sorted(set(row_symbols) - set(failed_symbols))
    completed_at = datetime.now(timezone.utc)
    SourceRunRepository(db_path).insert_run(
        SourceRun(
            source=source,
            data_type=data_type,
            status=derive_source_run_status(
                row_count=row_count,
                succeeded_symbols=succeeded_symbols,
                failed_symbols=failed_symbols,
            ),
            attempted_at=attempted_at,
            completed_at=completed_at,
            requested_symbols=requested_symbols,
            succeeded_symbols=succeeded_symbols,
            failed_symbols=failed_symbols,
            failure_reasons=failure_reasons,
            row_count=row_count,
            latest_observed_at=latest_observed_at,
        )
    )


def _latest_price_observed_at(bars: list) -> datetime | None:
    if not bars:
        return None
    latest_date = max(bar.date for bar in bars)
    return datetime.combine(latest_date, datetime.min.time(), tzinfo=timezone.utc)


def _latest_news_observed_at(items: list) -> datetime | None:
    dated_items = [item.published_at for item in items if item.published_at]
    if not dated_items:
        return None
    return max(dated_items)
```

- [ ] **Step 4: Record source runs in price collection**

In the `collect prices` branch, set `attempted_at = datetime.now(timezone.utc)` immediately after `initialize_database(args.db)`.

After `PriceRepository(args.db).upsert_many(bars)`, add:

```python
        requested_symbols = sorted({bar.symbol for bar in bars}) if args.csv else symbols
        _record_source_run(
            db_path=args.db,
            source="csv_import" if args.csv else "yfinance",
            data_type="prices",
            attempted_at=attempted_at,
            requested_symbols=requested_symbols,
            row_symbols=[bar.symbol for bar in bars],
            failed_symbols=failed_symbols,
            failure_reasons=failure_reasons,
            row_count=len(bars),
            latest_observed_at=_latest_price_observed_at(bars),
        )
```

- [ ] **Step 5: Record source runs in news collection**

In the `collect news` branch, set `attempted_at = datetime.now(timezone.utc)` immediately after `initialize_database(args.db)`.

After `NewsRepository(args.db).upsert_many(collection.items)`, add:

```python
        _record_source_run(
            db_path=args.db,
            source="google_news_rss",
            data_type="news",
            attempted_at=attempted_at,
            requested_symbols=symbols,
            row_symbols=[item.related_symbol for item in collection.items],
            failed_symbols=collection.failed_symbols,
            failure_reasons=collection.failure_reasons,
            row_count=len(collection.items),
            latest_observed_at=_latest_news_observed_at(collection.items),
        )
```

- [ ] **Step 6: Run CLI tests**

Run: `python -m pytest tests/test_cli.py -v`

Expected: PASS.

---

### Task 3: Add Source Health To Data Coverage

**Files:**
- Modify: `app/analyzers/data_coverage_analyzer.py`
- Modify: `tests/test_data_coverage_analyzer.py`

- [ ] **Step 1: Add data coverage tests**

Add imports to `tests/test_data_coverage_analyzer.py`:

```python
from datetime import datetime, timezone

from app.models.source_run import SourceRun
```

Add tests:

```python
def test_data_coverage_includes_source_health_rows_and_partial_impacts():
    source_run = SourceRun(
        source="yfinance",
        data_type="prices",
        status="partial_success",
        attempted_at=datetime(2026, 7, 8, 1, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 7, 8, 1, 1, tzinfo=timezone.utc),
        requested_symbols=["SPY", "QQQ"],
        succeeded_symbols=["SPY"],
        failed_symbols=["QQQ"],
        failure_reasons={"QQQ": "YFRateLimitError: Too Many Requests"},
        row_count=120,
        latest_observed_at=datetime(2026, 7, 7, 0, 0, tzinfo=timezone.utc),
    )

    result = analyze_data_coverage(
        price_history={},
        price_symbols=[],
        macro_symbols=[],
        popular_company_symbols=[],
        news_item_count=0,
        source_runs=[source_run],
        as_of=datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc),
    )

    row = _row(result, "Source Health", "prices:yfinance")
    assert row.status == "partial_success"
    assert row.rows == 120
    assert row.latest == "2026-07-07T00:00:00+00:00"
    assert "QQQ: YFRateLimitError: Too Many Requests" in row.detail
    assert (
        "Price source yfinance partially succeeded; affected symbols may be stale or missing."
        in result.impacts
    )


def test_data_coverage_reports_failed_and_stale_source_runs():
    failed_news = SourceRun(
        source="google_news_rss",
        data_type="news",
        status="failed",
        attempted_at=datetime(2026, 7, 8, 1, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 7, 8, 1, 1, tzinfo=timezone.utc),
        requested_symbols=["SPY"],
        succeeded_symbols=[],
        failed_symbols=["SPY"],
        failure_reasons={"SPY": "URLError: timed out"},
        row_count=0,
        latest_observed_at=None,
    )
    stale_prices = SourceRun(
        source="yfinance",
        data_type="prices",
        status="success",
        attempted_at=datetime(2026, 7, 1, 1, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 7, 1, 1, 1, tzinfo=timezone.utc),
        requested_symbols=["SPY"],
        succeeded_symbols=["SPY"],
        failed_symbols=[],
        failure_reasons={},
        row_count=120,
        latest_observed_at=datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
    )

    result = analyze_data_coverage(
        price_history={},
        price_symbols=[],
        macro_symbols=[],
        popular_company_symbols=[],
        news_item_count=0,
        source_runs=[failed_news, stale_prices],
        as_of=datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc),
    )

    assert _row(result, "Source Health", "news:google_news_rss").status == "failed"
    assert _row(result, "Source Health", "prices:yfinance").status == "stale"
    assert (
        "News source google_news_rss failed; Sections 5-6 may be empty or stale."
        in result.impacts
    )
    assert (
        "Price source yfinance is stale; latest observed data is older than 3 days."
        in result.impacts
    )
```

- [ ] **Step 2: Run data coverage tests to verify failure**

Run: `python -m pytest tests/test_data_coverage_analyzer.py -v`

Expected: FAIL because `analyze_data_coverage` does not accept `source_runs`.

- [ ] **Step 3: Update analyzer signature and helpers**

In `app/analyzers/data_coverage_analyzer.py`, add imports:

```python
from datetime import datetime, timezone

from app.models.source_run import SourceRun
```

Add constants:

```python
PRICE_STALE_DAYS = 3
NEWS_STALE_DAYS = 2
```

Change the function signature:

```python
def analyze_data_coverage(
    price_history: dict[str, list[PriceBar]],
    price_symbols: list[str],
    macro_symbols: list[str],
    popular_company_symbols: list[str],
    news_item_count: int,
    source_runs: list[SourceRun] | None = None,
    as_of: datetime | None = None,
) -> DataCoverage:
```

Inside the function, after `rows.append(_news_row(news_item_count))`, add:

```python
    current_time = as_of or datetime.now(timezone.utc)
    if source_runs:
        rows.extend(_source_health_row(run, current_time) for run in source_runs)
```

Add helper functions:

```python
def _source_health_row(run: SourceRun, as_of: datetime) -> DataCoverageRow:
    status = _source_health_status(run, as_of)
    return DataCoverageRow(
        category="Source Health",
        item=f"{run.data_type}:{run.source}",
        status=status,
        rows=run.row_count,
        latest=run.latest_observed_at.isoformat() if run.latest_observed_at else "N/A",
        detail=_source_health_detail(run),
    )


def _source_health_status(run: SourceRun, as_of: datetime) -> str:
    if run.status != "success":
        return run.status
    if run.latest_observed_at is None:
        return "stale"
    stale_days = PRICE_STALE_DAYS if run.data_type == "prices" else NEWS_STALE_DAYS
    if (as_of - run.latest_observed_at).days > stale_days:
        return "stale"
    return "available"


def _source_health_detail(run: SourceRun) -> str:
    if run.failure_reasons:
        failures = "; ".join(
            f"{symbol}: {reason}"
            for symbol, reason in sorted(run.failure_reasons.items())
        )
        return f"Failed: {failures}"
    return f"Latest {run.source} collection status: {run.status}."
```

- [ ] **Step 4: Update impacts**

In `_impacts`, after news impact logic, add:

```python
    for row in rows:
        if row.category != "Source Health":
            continue
        data_type, source = row.item.split(":", 1)
        if row.status == "partial_success" and data_type == "prices":
            impacts.append(
                f"Price source {source} partially succeeded; affected symbols may be stale or missing."
            )
        elif row.status == "partial_success" and data_type == "news":
            impacts.append(
                f"News source {source} partially succeeded; Sections 5-6 may be incomplete."
            )
        elif row.status == "failed" and data_type == "prices":
            impacts.append(
                f"Price source {source} failed; price-driven sections may be stale or empty."
            )
        elif row.status == "failed" and data_type == "news":
            impacts.append(
                f"News source {source} failed; Sections 5-6 may be empty or stale."
            )
        elif row.status == "stale" and data_type == "prices":
            impacts.append(
                f"Price source {source} is stale; latest observed data is older than {PRICE_STALE_DAYS} days."
            )
        elif row.status == "stale" and data_type == "news":
            impacts.append(
                f"News source {source} is stale; latest observed item is older than {NEWS_STALE_DAYS} days."
            )
```

- [ ] **Step 5: Run data coverage tests**

Run: `python -m pytest tests/test_data_coverage_analyzer.py -v`

Expected: PASS.

---

### Task 4: Wire Source Runs Into Daily Report Job

**Files:**
- Modify: `app/jobs/daily_market_job.py`
- Modify: `tests/test_markdown_writer.py` only if current coverage needs import adjustment.

- [ ] **Step 1: Import repository**

In `app/jobs/daily_market_job.py`, add:

```python
from app.storage.repositories.source_run_repo import SourceRunRepository
```

- [ ] **Step 2: Load source runs before Data Coverage**

After `recent_news = NewsRepository(db_path).get_recent_items()`, add:

```python
    source_runs = SourceRunRepository(db_path).get_recent_runs()
```

- [ ] **Step 3: Pass source runs to analyzer**

In `analyze_data_coverage(...)`, add:

```python
        source_runs=source_runs,
```

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_data_coverage_analyzer.py tests/test_markdown_writer.py tests/test_cli.py -v`

Expected: PASS.

---

### Task 5: Full Verification

**Files:**
- No edits.

- [ ] **Step 1: Run full tests**

Run: `python -m pytest -v`

Expected: PASS.

- [ ] **Step 2: Inspect status**

Run: `git status --short`

Expected: includes the new source-run model, repository, tests, schema changes, CLI changes, Data Coverage changes, daily job wiring, this plan, and the design doc. Pre-existing unrelated staged/untracked changes may still appear and must not be reverted.

---

## Self-Review

Spec coverage:

- Generic source-run model and storage are covered in Task 1.
- Existing collection paths record source runs in Task 2.
- Data Coverage source-health rows and impacts are covered in Task 3.
- Daily report job integration is covered in Task 4.
- Full verification is covered in Task 5.

Placeholder scan:

- No placeholder markers or undefined task references remain.

Type consistency:

- `SourceRun`, `SourceRunRepository`, `source_runs`, and `source_runs` function parameters are named consistently across tasks.
