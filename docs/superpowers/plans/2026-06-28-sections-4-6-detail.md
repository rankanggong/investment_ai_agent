# Sections 4-6 Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand Sections 4-6 with deterministic evidence and interpretation details from existing data.

**Architecture:** Add optional detail fields to existing analysis dataclasses, populate them inside existing analyzers, and expand markdown rendering. No new collectors, external APIs, or LLM calls are added.

**Tech Stack:** Python dataclasses, pytest, existing analyzer and markdown writer modules.

---

### Task 1: Analyzer Detail Fields

**Files:**
- Modify: `app/models/analysis.py`
- Modify: `app/analyzers/macro_context_analyzer.py`
- Modify: `app/analyzers/news_cluster_analyzer.py`
- Modify: `app/analyzers/fundamental_event_analyzer.py`
- Test: `tests/test_macro_context_analyzer.py`
- Test: `tests/test_news_cluster_analyzer.py`
- Test: `tests/test_fundamental_event_analyzer.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert macro evidence rows, cluster source details, and event review details exist.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_macro_context_analyzer.py tests/test_news_cluster_analyzer.py tests/test_fundamental_event_analyzer.py -v`

Expected: fail because the new detail fields do not exist yet.

- [ ] **Step 3: Implement fields and analyzer population**

Add optional dataclass fields with defaults. Populate details deterministically in each analyzer.

- [ ] **Step 4: Verify analyzer tests pass**

Run: `python -m pytest tests/test_macro_context_analyzer.py tests/test_news_cluster_analyzer.py tests/test_fundamental_event_analyzer.py -v`

Expected: pass.

### Task 2: Markdown Rendering

**Files:**
- Modify: `app/outputs/markdown_writer.py`
- Test: `tests/test_markdown_writer.py`

- [ ] **Step 1: Write failing rendering test**

Add a test that asserts Section 4 evidence rows, Section 5 why/source/manual-read details, and Section 6 review details render.

- [ ] **Step 2: Verify rendering test fails**

Run: `python -m pytest tests/test_markdown_writer.py -v`

Expected: fail because the extra details are not rendered yet.

- [ ] **Step 3: Implement expanded rendering**

Render macro evidence rows, cluster details, and fundamental event review fields.

- [ ] **Step 4: Run full verification**

Run: `git diff --check` and `python -m pytest -v`

Expected: no diff whitespace errors and all tests pass.
