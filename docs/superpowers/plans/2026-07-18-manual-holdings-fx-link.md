# Manual Holdings And FX Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CSV-based manual holding import entry point and automatically link USD holdings to compatible imported FX cash transactions.

**Architecture:** Store manual holding snapshots in the steward database and keep the linked cash-transaction ID as an auditable reference. A focused holding importer validates CSV rows, normalizes currencies, and selects the closest eligible positive USD FX transaction, preferring the same institution and account.

**Tech Stack:** Python dataclasses, standard-library CSV/decimal/datetime/sqlite3, argparse, pytest.

---

### Task 1: Holding Model And Storage

**Files:**
- Modify: `app/steward/models.py`
- Modify: `app/steward/storage.py`
- Test: `tests/test_steward_storage.py`

- [ ] **Step 1: Write a failing storage test**

Create a `Holding` with institution, account, symbol, name, quantity, currency, unit cost, acquisition date, and FX transaction ID; upsert it twice and assert one normalized `StoredHolding` is returned.

- [ ] **Step 2: Run the storage test and verify it fails**

Run: `pytest tests/test_steward_storage.py -v`

Expected: FAIL because `Holding` and holding repository methods do not exist.

- [ ] **Step 3: Add the holding schema and repository API**

Add `Holding` and `StoredHolding` dataclasses, a `steward_holdings` table keyed by institution/account/symbol/acquisition date, plus `upsert_holding` and `list_holdings` methods that preserve the optional linked statement transaction ID.

- [ ] **Step 4: Run the storage test and verify it passes**

Run: `pytest tests/test_steward_storage.py -v`

Expected: PASS.

### Task 2: CSV Import And USD FX Matching

**Files:**
- Create: `app/steward/holdings.py`
- Test: `tests/test_steward_holdings.py`

- [ ] **Step 1: Write failing import and matching tests**

Cover CSV validation, currency aliases, non-USD holdings remaining unlinked, USD holdings selecting a positive transaction whose summary contains `购汇`, and same-account preference over a merely closer cross-account transaction.

- [ ] **Step 2: Run the holding tests and verify they fail**

Run: `pytest tests/test_steward_holdings.py -v`

Expected: FAIL because the holding importer does not exist.

- [ ] **Step 3: Implement the importer and matcher**

Parse required columns `institution,account_label,symbol,name,quantity,currency,unit_cost,acquired_on`, reject invalid rows with row-numbered errors, normalize `美元` to `USD`, and link USD rows to the closest positive USD FX transaction on or before acquisition, preferring exact institution/account matches.

- [ ] **Step 4: Run the holding tests and verify they pass**

Run: `pytest tests/test_steward_holdings.py -v`

Expected: PASS.

### Task 3: CLI Entry Point And Documentation

**Files:**
- Modify: `app/main.py`
- Modify: `README.md`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write a failing CLI test**

Parse and execute `steward holding import --csv holdings.csv`, then assert the command reports imported and FX-linked counts.

- [ ] **Step 2: Run the CLI test and verify it fails**

Run: `pytest tests/test_cli.py -v`

Expected: FAIL because the holding command is not registered.

- [ ] **Step 3: Add the command and CSV contract documentation**

Wire the importer into argparse and document the required columns, idempotent behavior, currency normalization, and USD FX-link selection rules.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_cli.py tests/test_steward_storage.py tests/test_steward_holdings.py -v`

Expected: PASS.

### Task 4: Verification

- [ ] **Step 1: Run the complete suite**

Run: `pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run a no-network CLI smoke test**

Import a temporary holdings CSV into a temporary steward database and inspect the printed imported/linked counts.

- [ ] **Step 3: Review the plan against the request**

Confirm there is a discoverable manual import entry, USD holdings are automatically linked from imported FX facts, non-USD holdings are not linked, and unmatched USD rows remain importable and auditable.
