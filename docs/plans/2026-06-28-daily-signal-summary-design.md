# Daily Signal Summary Design

## Goal

Add a top-of-report triage section that tells the reader whether the day needs review, monitoring, or no action from the available research signals.

## Approach

The report should be triage-driven before it is section-driven. A new deterministic analyzer will combine existing outputs: price signals, sector rotation, macro context, news clusters, and fundamental events. It will produce a small `DailySignalSummary` model with a status, drivers, and a concise reason.

## Status Rules

`review_required` is used when the report has clear material signals: unusual price moves or detected fundamental events.

`monitor` is used when the report has weaker but still useful context: important news clusters, a macro pressure/support regime, or a meaningful sector rotation score.

`no_material_signal` is used when nothing crosses those thresholds.

The analyzer does not produce buy/sell advice and does not require portfolio holdings. It only explains whether the research output deserves attention.

## Rendering

The markdown writer will render the summary as `## 0. What Matters Today` above Section 1. The section will show:

- `Status`
- `Drivers`
- `Reason`

When data is unavailable, the drivers should say so explicitly, for example `Macro: unknown` or `News: no important clusters`.

## Testing

Tests will cover the summary analyzer and markdown rendering. The daily job will pass the computed summary into `render_daily_report`.
