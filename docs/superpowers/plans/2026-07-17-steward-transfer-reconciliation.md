# Steward Transfer Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile statement transactions into confirmed or suggested internal transfers so steward reports separate account movement from external household cashflow.

**Architecture:** Keep imported statement transactions immutable. Add a reconciliation module with one interface that accepts transactions, owned-account profiles, and persisted decisions, then returns confirmed and suggested transfer matches. The analyzer consumes that result; only confirmed matches are excluded from external cashflow, while gross statement cashflow remains visible.

**Tech Stack:** Python dataclasses, SQLite, argparse, pytest, Markdown reporting.

---

### Task 1: Reconciliation Domain Model

**Files:**
- Create: `app/steward/reconciliation.py`
- Modify: `app/steward/models.py`
- Test: `tests/test_steward_reconciliation.py`

- [ ] **Step 1: Write failing tests for conservative matching**

Test that equal and opposite transactions between two owned accounts within three days produce one suggested match, while unknown accounts and mismatched currencies do not.

- [ ] **Step 2: Run the reconciliation tests and verify they fail because the module is absent**

Run: `pytest tests/test_steward_reconciliation.py -v`
Expected: FAIL with an import error for `app.steward.reconciliation`.

- [ ] **Step 3: Implement the minimal reconciliation interface**

Add account profiles, transfer decisions, transfer matches, and `reconcile_transfers(transactions, accounts, decisions)`. Match one outgoing leg to at most one incoming leg using ownership, currency, amount, and date distance. Persisted confirmation or rejection overrides suggestions.

- [ ] **Step 4: Run the reconciliation tests**

Run: `pytest tests/test_steward_reconciliation.py -v`
Expected: PASS.

### Task 2: Persist Accounts And Decisions

**Files:**
- Modify: `app/steward/storage.py`
- Test: `tests/test_steward_storage.py`

- [ ] **Step 1: Write failing repository tests**

Test account-profile upsert/list behavior and confirmed/rejected transfer-decision upsert/list behavior.

- [ ] **Step 2: Run the storage tests and verify missing methods fail**

Run: `pytest tests/test_steward_storage.py -v`
Expected: FAIL because account and decision repository methods do not exist.

- [ ] **Step 3: Add additive SQLite tables and repository methods**

Add `steward_accounts` and `steward_transfer_decisions`. Include transaction row IDs in stored transaction objects so decisions can reference stable imported rows.

- [ ] **Step 4: Run the storage tests**

Run: `pytest tests/test_steward_storage.py -v`
Expected: PASS.

### Task 3: Reconciled Analysis And Report

**Files:**
- Modify: `app/steward/analyzer.py`
- Modify: `app/steward/markdown_writer.py`
- Modify: `app/steward/job.py`
- Test: `tests/test_steward_job.py`

- [ ] **Step 1: Write failing analysis and report tests**

Test that confirmed transfer legs remain in statement cashflow but are excluded from external cashflow, and that suggested transfers appear as manual checks without changing totals.

- [ ] **Step 2: Run the job tests and verify the new assertions fail**

Run: `pytest tests/test_steward_job.py -v`
Expected: FAIL because reconciled cashflow and transfer report sections are absent.

- [ ] **Step 3: Integrate reconciliation into report generation**

Expose both statement and external cashflow totals. Add confirmed-transfer and transfer-candidate sections with transaction IDs, dates, accounts, currencies, amounts, and decision status.

- [ ] **Step 4: Run the job tests**

Run: `pytest tests/test_steward_job.py -v`
Expected: PASS.

### Task 4: Manual Review CLI

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Test `steward account set` and `steward transfer confirm|reject` parsing and repository delegation.

- [ ] **Step 2: Run CLI tests and verify command parsing fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL because the commands are not registered.

- [ ] **Step 3: Implement CLI commands**

Validate ownership and role choices, store account profiles, and store transfer decisions by outgoing and incoming statement transaction IDs.

- [ ] **Step 4: Run CLI tests**

Run: `pytest tests/test_cli.py -v`
Expected: PASS.

### Task 5: Full Verification

**Files:**
- Modify: `docs/plans/2026-07-15-portfolio-fx-steward-design.md`

- [ ] **Step 1: Update the steward design document**

Record the immutable-statement/economic-event distinction, conservative matching criteria, and confirmed-only exclusion rule.

- [ ] **Step 2: Run the complete test suite**

Run: `pytest -q`
Expected: all tests pass with zero failures.

- [ ] **Step 3: Run a temporary end-to-end CLI smoke test**

Initialize a temporary database, import a synthetic pair, register accounts, confirm the suggested transfer, and generate a report. Verify the report shows zero external net cashflow and the unchanged gross statement movements.
