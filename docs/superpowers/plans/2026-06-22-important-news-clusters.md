# Important News Clusters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google News RSS collection, SQLite persistence, deterministic clustering, and daily report rendering for important news clusters.

**Architecture:** A collector normalizes Google News RSS items into `NewsItem` records, a repository persists them, and a deterministic analyzer groups recent stored items into `NewsCluster` values for the report. The CLI collects news separately from prices, and `report daily` renders existing stored clusters.

**Tech Stack:** Python 3.11+, stdlib `urllib`, `xml.etree.ElementTree`, `email.utils`, `sqlite3`, dataclasses, pytest

---

### Task 1: News Models And Google RSS Collector

**Files:**
- Modify: `app/models/analysis.py`
- Create: `app/collectors/google_news_collector.py`
- Create: `tests/test_google_news_collector.py`

- [ ] Write failing tests for RSS item normalization and symbol-level fetch failure reporting.
- [ ] Run `python -m pytest tests/test_google_news_collector.py -v` and confirm missing collector failure.
- [ ] Implement `NewsItem`, `NewsCollectionResult`, and `collect_google_news(symbols, fetcher=None)`.
- [ ] Run `python -m pytest tests/test_google_news_collector.py -v` and confirm passing tests.

### Task 2: News Storage

**Files:**
- Modify: `app/storage/schema.sql`
- Create: `app/storage/repositories/news_repo.py`
- Create: `tests/test_news_storage.py`

- [ ] Write failing repository tests for upsert-by-normalized-url and recent item retrieval.
- [ ] Run `python -m pytest tests/test_news_storage.py -v` and confirm expected failure.
- [ ] Add `news_items` table and `NewsRepository`.
- [ ] Run `python -m pytest tests/test_news_storage.py -v` and confirm passing tests.

### Task 3: News Cluster Analyzer

**Files:**
- Modify: `app/models/analysis.py`
- Create: `app/analyzers/news_cluster_analyzer.py`
- Create: `tests/test_news_cluster_analyzer.py`

- [ ] Write failing analyzer tests for deduplication, symbol grouping, representative headlines, and confidence.
- [ ] Run `python -m pytest tests/test_news_cluster_analyzer.py -v` and confirm expected failure.
- [ ] Implement `NewsCluster` and `analyze_news_clusters(items, max_clusters=5)`.
- [ ] Run `python -m pytest tests/test_news_cluster_analyzer.py -v` and confirm passing tests.

### Task 4: CLI Collection

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_cli.py`

- [ ] Write failing CLI tests for `collect news --google-rss`, watchlist defaults, explicit symbols, persistence, and failure reporting.
- [ ] Run `python -m pytest tests/test_cli.py -v` and confirm expected failure.
- [ ] Add news collection CLI dispatch using `NewsRepository`.
- [ ] Run `python -m pytest tests/test_cli.py -v` and confirm passing tests.

### Task 5: Report Rendering And Job Integration

**Files:**
- Modify: `app/outputs/markdown_writer.py`
- Modify: `app/jobs/daily_market_job.py`
- Modify: `tests/test_markdown_writer.py`

- [ ] Write failing rendering test for `## 5. Important News Clusters`.
- [ ] Run `python -m pytest tests/test_markdown_writer.py -v` and confirm expected failure.
- [ ] Add optional `news_clusters` rendering.
- [ ] Wire `NewsRepository.get_recent_items()` and `analyze_news_clusters()` into `generate_daily_report`.
- [ ] Run `python -m pytest -v` and confirm all tests pass.
- [ ] Run `git diff --check` and review final diff.

