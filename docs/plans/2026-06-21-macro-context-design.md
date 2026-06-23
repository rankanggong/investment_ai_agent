# Macro Context Design

## Goal

Add a first macro context section to the daily market report using existing price-derived proxy signals only.

## Scope

This version does not add FRED, Treasury, BLS, or any new data storage. It reuses the current watchlist and price pipeline. The macro analyzer reads `PriceSignal` values for existing proxies:

- `TLT` for duration/rate pressure
- `UUP` for USD direction
- `HYG` and `LQD` for credit risk appetite
- `GLD` for gold context
- `SPY` as broad risk reference

## Architecture

Add a `MacroContext` dataclass to `app/models/analysis.py` and a focused analyzer in `app/analyzers/macro_context_analyzer.py`. The daily report job will compute macro context from the same `signals` dictionary already used for price moves and sector rotation.

The report writer will accept an optional `MacroContext`. If present, it renders deterministic labels and notes under `## 4. Macro Context`; otherwise it preserves the current deferred placeholder.

## Labels

The analyzer produces:

- `rates_context`: `duration_supported`, `rates_pressure`, `mixed`, or `unknown`
- `usd_context`: `usd_strengthening`, `usd_weakening`, `mixed`, or `unknown`
- `credit_context`: `risk_appetite_supportive`, `credit_stress`, `mixed`, or `unknown`
- `gold_context`: `gold_supported`, `gold_pressure`, `mixed`, or `unknown`
- `overall_regime`: concise summary derived from risk proxies

## Testing

Tests cover deterministic macro labels from synthetic `PriceSignal` inputs and Markdown rendering in the daily report. No network-dependent tests are added.

