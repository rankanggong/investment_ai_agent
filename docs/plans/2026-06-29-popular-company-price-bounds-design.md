# Popular Company Price Bounds Design

## Goal

Add Section 9 to the daily report with higher/lower review bands for popular companies.

## Scope

This stage uses only locally stored daily price history. It does not estimate intrinsic value, fair value, or target price from fundamentals. The report must label the output as price-derived review bands.

## Watchlist

Add a `popular_companies` group to `config/watchlist.yaml`:

- AAPL
- MSFT
- NVDA
- AMZN
- GOOGL
- META
- TSLA

These symbols are collected by the existing price collector because the collector already uses the watchlist.

## Analyzer

Add `analyze_company_price_bounds(price_history, symbols)`.

For each symbol with enough history:

- Latest close: most recent close.
- Lower review bound: the lower of the recent close range and one volatility band below latest close.
- Upper review bound: the higher of the recent close range and one volatility band above latest close.
- Basis: `60D range + volatility band`, or shorter available history if fewer than 60 bars.
- Confidence: capped by available history length, reaching `1.00` at 60 bars.

Symbols with fewer than 20 bars are omitted and recorded as notes.

## Report

Append Section 9:

```markdown
## 9. Popular Company Price Bounds

Research support only. These are price-derived review bands, not intrinsic value.

| Company | Latest | Lower Review Bound | Upper Review Bound | Basis | Confidence |
|---|---:|---:|---:|---|---:|
```

If no bounds are available, render a no-data message plus notes.

## Testing

Tests cover:

- Analyzer bound calculation and confidence.
- Analyzer notes for insufficient history.
- Watchlist group presence.
- Markdown rendering.
- Daily job wiring.
