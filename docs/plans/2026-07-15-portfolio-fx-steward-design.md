# Portfolio And FX Steward Design

## Goal

Build a first-stage steward module that runs independently from the current daily
market report. It ingests manually downloaded bank, payment, and future
brokerage files from a local folder, normalizes them into auditable records, and
produces a portfolio/cash/FX state report for review.

## Stage 1 Boundary

Stage 1 handles local files only. Email monitoring, brokerage APIs, automatic
trading, and automatic FX conversion are out of scope.

The initial sample files are cash transaction statements rather than brokerage
position files:

- Alipay CSV transaction detail export.
- China Merchants Bank transaction PDF.
- ICBC debit account transaction PDF.

Therefore the first working slice is a cash transaction steward. It should
normalize statement rows, preserve source-document traceability, summarize cash
balances and cashflow by account/currency, and flag rows requiring manual review.
Portfolio holdings and brokerage-specific parsers can be added later under the
same module.

## Architecture

```text
data/steward/inbox/
  -> source document fingerprinting
  -> parser registry
  -> normalized cash transactions
  -> steward SQLite database
  -> transfer reconciliation
  -> cash/FX exposure analyzer
  -> Markdown steward report
```

The steward remains independent by using its own package namespace and database
initialization path. It may share project conventions such as dataclasses,
SQLite repositories, CLI commands, and Markdown output.

## Data Model

Stage 1 stores:

- `steward_source_documents`: file path, SHA-256 fingerprint, source type,
  institution, imported timestamp, and parser status.
- `steward_cash_transactions`: normalized transaction rows with institution,
  account label, transaction date/time, currency, signed amount, balance,
  summary, channel, source document hash, and raw text.
- `steward_accounts`: explicit account ownership and role by institution,
  account label, and currency.
- `steward_transfer_decisions`: confirmed or rejected links between one outgoing
  and one incoming statement transaction.
- `steward_reports`: generated Markdown report content.

Statement transactions remain immutable facts. Reconciliation interprets one or
more facts as an economic event without rewriting the imported records. It does
not infer investment positions from cashflow labels.

## Transfer Reconciliation

A transfer candidate requires:

- Two distinct accounts registered as owned.
- Equal currencies and opposite amount directions.
- Dates no more than three days apart.
- An incoming amount no greater than the outgoing amount, with a difference no
  greater than one currency unit or 0.1%, whichever is larger.
- One-to-one use of statement transactions.

Automatic matching creates suggestions only. A suggestion remains in external
cashflow until manually confirmed. Rejected pairs are suppressed. Confirmed
pairs remain valid only while both accounts are registered as owned; missing or
incompatible rows are reported as reconciliation warnings.

For a confirmed transfer, both statement legs are excluded from external
cashflow, while any difference between the outgoing and incoming amounts is
retained as a fee outflow. Statement cashflow continues to show the original
gross movements for audit.

## Parser Contracts

Each parser returns normalized `CashTransaction` objects and parser warnings.
Parsers must be deterministic and conservative:

- Parse only rows matching known statement structures.
- Preserve source text for audit.
- Emit warnings when the document is recognized but rows cannot be parsed.
- Never classify a row as investment, income, expense, or transfer unless a
  deterministic rule is added and tested.

For PDFs, the core parser accepts extracted text. PDF extraction is a thin
adapter so tests do not depend on a PDF library. If `pypdf` is unavailable, the
CLI reports the missing optional dependency instead of failing obscurely.

## Report Contract

```markdown
# Portfolio Steward Report - YYYY-MM-DD

Research support only. Not investment, trading, tax, or FX execution advice.

## 0. State Summary
## 1. Data Coverage
## 2. Account Balances
## 3. External Cashflow By Currency
## 4. Statement Cashflow By Currency
## 5. Confirmed Internal Transfers
## 6. Transfer Candidates
## 7. Recent Cash Transactions
## 8. FX Review
## 9. Exceptions / Manual Checks
```

FX review is exposure-based. It can state that balances are only available in
one currency, that a currency has excess/short cash versus configured bands, or
that no FX suggestion can be made due to missing targets. It must not instruct
the user to execute a conversion.

## Later Stages

Later stages can add:

- Email attachment monitor that writes to the same local inbox.
- Brokerage position parsers.
- Target currency bands and upcoming liability calendars.
- Security/export hygiene for sensitive files.
- Optional integration into the existing daily report.
