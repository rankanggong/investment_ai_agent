# Portfolio And FX Steward Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent stage-1 steward module that imports local bank/payment transaction statements and generates a cash/FX review report.

**Architecture:** Add a new `app.steward` package with parser, storage, analyzer, report, and job layers. The CLI exposes `steward init-db`, `steward import`, and `steward report` without coupling to the daily market job.

**Tech Stack:** Python dataclasses, standard-library CSV/regex/hashlib/sqlite3, optional `pypdf` for PDF text extraction, pytest.

---

### Task 1: Parser Models And Statement Parsers

**Files:**
- Create: `app/steward/models.py`
- Create: `app/steward/parsers/alipay.py`
- Create: `app/steward/parsers/cmb.py`
- Create: `app/steward/parsers/icbc.py`
- Create: `app/steward/parsers/registry.py`
- Test: `tests/test_steward_parsers.py`

- [ ] Write failing tests for one sanitized CMB row, one sanitized ICBC row, and one sanitized Alipay CSV row.
- [ ] Run `pytest tests/test_steward_parsers.py -v` and verify the imports fail because the modules do not exist.
- [ ] Implement `CashTransaction`, `ParseResult`, and deterministic parser functions.
- [ ] Run `pytest tests/test_steward_parsers.py -v` and verify all parser tests pass.

### Task 2: Steward Storage

**Files:**
- Create: `app/steward/storage.py`
- Test: `tests/test_steward_storage.py`

- [ ] Write a failing repository test that initializes steward tables, records a source document, upserts transactions, and verifies duplicate source hashes are ignored.
- [ ] Run `pytest tests/test_steward_storage.py -v` and verify it fails because storage does not exist.
- [ ] Implement `initialize_steward_database` and `StewardRepository`.
- [ ] Run `pytest tests/test_steward_storage.py -v` and verify it passes.

### Task 3: Import Job, Analyzer, And Markdown Report

**Files:**
- Create: `app/steward/job.py`
- Create: `app/steward/analyzer.py`
- Create: `app/steward/markdown_writer.py`
- Test: `tests/test_steward_job.py`

- [ ] Write failing tests for importing a local CSV file and rendering a report summary from stored transactions.
- [ ] Run `pytest tests/test_steward_job.py -v` and verify it fails because the job/report functions do not exist.
- [ ] Implement inbox scanning, SHA-256 fingerprinting, parser dispatch, cash summary analysis, and Markdown rendering.
- [ ] Run `pytest tests/test_steward_job.py -v` and verify it passes.

### Task 4: CLI Integration

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_cli.py`

- [ ] Add a failing CLI parser test for `steward init-db`, `steward import`, and `steward report`.
- [ ] Run `pytest tests/test_cli.py -v` and verify the new test fails.
- [ ] Add CLI subcommands that call the steward job functions.
- [ ] Run `pytest tests/test_cli.py tests/test_steward_*.py -v` and verify they pass.

### Task 5: Verification

- [ ] Run `pytest -q`.
- [ ] Run a no-network smoke command against an empty temporary inbox.
- [ ] Document any optional PDF dependency limitation in the final response.
