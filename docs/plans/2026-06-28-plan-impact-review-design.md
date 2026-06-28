# Plan Impact Review Design

## Goal

Implement Section 7 as a position-agnostic impact review. It should identify assets that deserve accumulation review or de-risk review from the available research evidence, without issuing buy or sell instructions.

## Scope

This first stage does not know holdings, cost basis, target allocation, cash level, tax constraints, or risk limits. It therefore cannot decide what the user should buy or sell. It can rank watchlist assets by evidence strength and explain why they deserve review.

## Output

Section 7 renders:

- A research-support disclaimer.
- `High-conviction accumulation review` candidates.
- `High-conviction de-risk review` candidates.
- `No clear plan impact` when no asset crosses a threshold.

The report must not use wording such as `buy`, `sell`, `must`, `without doubt`, or `without hesitation`.

## Analyzer

Add a deterministic `analyze_plan_impact(...)` function. It consumes:

- `PriceSignal` values.
- `SectorRotation`.
- `MacroContext`.
- `NewsCluster` values.
- `FundamentalEvent` values.

The analyzer scores each symbol from available evidence:

- Positive price trend or constructive unusual move adds evidence.
- Negative price trend or adverse unusual move subtracts evidence.
- Macro regime support or pressure affects broad-market assets and relevant macro proxies.
- Sector strength or weakness affects sector symbols.
- News clusters add lightweight review evidence.
- Fundamental events add review evidence, with regulatory events treated as de-risk evidence.

Candidates with scores at or above `2` enter accumulation review. Candidates with scores at or below `-2` enter de-risk review.

## Data Model

Add:

- `PlanImpactItem(symbol, score, evidence)`
- `PlanImpact(accumulation_review, derisk_review, notes)`

## Testing

Tests should cover:

- Positive evidence creating an accumulation review candidate.
- Negative evidence creating a de-risk review candidate.
- Quiet or insufficient evidence producing no clear impact.
- Markdown rendering that replaces the old Section 7 placeholder.
