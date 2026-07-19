# Disable News And Focus Data Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disable RSS/news collection and news-derived report generation so the product focuses on market-price analysis and personal portfolio/cash state.

**Architecture:** Remove news from the active CLI and daily-report orchestration while leaving the collector, repository, schema, and historical rows intact for reversibility. Make report summaries, coverage diagnostics, and Markdown sections data-only; the independent steward workflow remains the source of personal cash and account analysis.

**Tech Stack:** Python 3.11+, argparse, SQLite, pytest, Markdown

---

### Task 1: Disable The News Collection Entry Point

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI test**

Replace the positive RSS parser assertion with a test that `collect news` is rejected:

```python
def test_cli_does_not_expose_news_collection():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["collect", "news", "--google-rss"])
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `.venv/bin/pytest tests/test_cli.py::test_cli_does_not_expose_news_collection -v`

Expected: FAIL because `collect news --google-rss` still parses successfully.

- [ ] **Step 3: Remove the active RSS command**

Delete the Google News collector and repository imports, the `collect news` parser, and the `collect/news` dispatch branch from `app/main.py`. Delete the two obsolete RSS CLI execution tests and their news-only imports from `tests/test_cli.py`; collector and repository unit tests remain because dormant code and stored data are intentionally retained.

- [ ] **Step 4: Run CLI tests**

Run: `.venv/bin/pytest tests/test_cli.py -v`

Expected: PASS, with price, report, and steward commands still exposed.

### Task 2: Remove News From Daily Report Orchestration

**Files:**
- Modify: `app/jobs/daily_market_job.py`
- Modify: `tests/test_markdown_writer.py`

- [ ] **Step 1: Add a report-level regression test**

Add assertions to the daily report test that the rendered Markdown excludes all news-derived headings and messages:

```python
assert "Important News Clusters" not in content
assert "Fundamental Events" not in content
assert "What To Read Manually" not in content
assert "stored news" not in content.lower()
```

- [ ] **Step 2: Run the focused Markdown test and verify it fails**

Run: `.venv/bin/pytest tests/test_markdown_writer.py -v`

Expected: FAIL because the report still emits news and fundamental-event sections.

- [ ] **Step 3: Stop reading and analyzing news in the daily job**

Remove `NewsRepository`, `analyze_news_clusters`, and `analyze_fundamental_events` from `app/jobs/daily_market_job.py`. Pass empty news/event lists only to existing scoring interfaces that still accept them, so dormant domain types do not need a destructive migration.

- [ ] **Step 4: Run the daily job and Markdown tests**

Run: `.venv/bin/pytest tests/test_markdown_writer.py tests/test_cli.py -v`

Expected: PASS and no runtime path reads the `news_items` table.

### Task 3: Make Summaries And Coverage Data-Only

**Files:**
- Modify: `app/analyzers/daily_signal_summary_analyzer.py`
- Modify: `app/analyzers/data_coverage_analyzer.py`
- Modify: `tests/test_daily_signal_summary_analyzer.py`
- Modify: `tests/test_data_coverage_analyzer.py`

- [ ] **Step 1: Update summary expectations**

Change tests to call `analyze_daily_signal_summary` with price, sector, and macro arguments only. Assert drivers contain no `News:` or `Fundamental events:` values and the neutral reason is:

```python
"No price, sector, or macro signal crossed review thresholds."
```

- [ ] **Step 2: Update coverage expectations**

Remove `news_item_count` from test calls and assert no coverage row has category `News`; company-bound rows use category `Company bounds` and impacts refer to that name instead of report section numbers.

- [ ] **Step 3: Run analyzer tests and verify they fail**

Run: `.venv/bin/pytest tests/test_daily_signal_summary_analyzer.py tests/test_data_coverage_analyzer.py -v`

Expected: FAIL because production APIs and output still include news.

- [ ] **Step 4: Simplify the analyzers**

Remove news/fundamental parameters, drivers, and threshold logic from `analyze_daily_signal_summary`. Remove news count, news coverage rows, and news impacts from `analyze_data_coverage`; rename the company category from `Section 9` to `Company bounds`.

- [ ] **Step 5: Run analyzer tests**

Run: `.venv/bin/pytest tests/test_daily_signal_summary_analyzer.py tests/test_data_coverage_analyzer.py -v`

Expected: PASS.

### Task 4: Render A Data-Focused Report

**Files:**
- Modify: `app/outputs/markdown_writer.py`
- Modify: `tests/test_markdown_writer.py`
- Modify: `README.md`

- [ ] **Step 1: Remove news-derived report inputs and sections**

Delete `news_clusters` and `fundamental_events` from `render_daily_report`, remove sections for important news clusters, fundamental events, and manual reading, and renumber the remaining sections:

```text
## 5. Impact On My Plan
## 6. Popular Company Price Bounds
```

Delete now-unused private rendering helpers and news model imports from the writer.

- [ ] **Step 2: Update Markdown tests**

Remove fixtures and tests whose only purpose is rendering news/fundamental content. Update plan-impact and company-bound heading assertions to sections 5 and 6, while retaining the analyzer/storage unit tests for dormant news code.

- [ ] **Step 3: Document the active product scope**

Update `README.md` to state that the active workflow is intentionally data-first: market prices and personal cash/account analysis are enabled, while RSS/news collection and news-derived report sections are disabled.

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/pytest -q`

Expected: all tests pass.

- [ ] **Step 5: Inspect the CLI and a generated report**

Run: `.venv/bin/python -m app.main collect --help`

Expected: only the `prices` collection command is listed.

Run: `.venv/bin/python -m app.main report daily --db data/finance.db --watchlist config/watchlist.yaml --report-dir /tmp/investment-ai-agent-reports`

Expected: a report is written successfully and contains market/data sections but no RSS, news, headline, or fundamental-event section.

