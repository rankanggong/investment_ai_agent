# Data Coverage Diagnostics Design

## Goal

Add a top-of-report data coverage section that explains whether quiet or unknown report sections are caused by missing data.

## Placement

Render `## Data Coverage` immediately after `## 0. What Matters Today` and before Section 1.

## Inputs

Use data already available during daily report generation:

- Watchlist symbols and groups.
- Price history loaded from SQLite.
- Stored recent news rows.
- Known analyzer minimum requirements.

No new collectors, network calls, or schema changes are needed.

## Rules

Price rows:

- `available`: at least one row.
- `missing`: zero rows.

Macro rows:

- `available`: at least six rows for each macro proxy, enough for a 5D return.
- `insufficient`: one to five rows.
- `missing`: zero rows.

Popular company bounds:

- `available`: at least twenty rows.
- `insufficient`: one to nineteen rows.
- `missing`: zero rows.

News:

- `available`: at least one stored recent news row.
- `missing`: zero rows.

## Output

The model contains table rows plus impact notes. Example:

```markdown
## Data Coverage

| Category | Item | Status | Rows | Latest | Detail |
|---|---|---:|---:|---|---|
| Macro | UUP | missing | 0 | N/A | Needs at least 6 price rows for 5D macro context. |

Impact:
- Section 4 may be unknown because UUP is missing.
```

## Testing

Tests cover analyzer status classification, impact notes, markdown rendering, and daily job wiring by full-suite import coverage.
