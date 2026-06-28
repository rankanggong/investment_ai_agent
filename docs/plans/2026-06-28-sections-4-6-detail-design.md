# Sections 4-6 Detail Design

## Goal

Make report Sections 4-6 more useful by showing the evidence and interpretation behind macro labels, news clusters, and fundamental events.

## Scope

This stage uses only data already available to the report pipeline:

- Price-derived `PriceSignal` values.
- Stored Google News RSS `NewsItem` values.
- Existing deterministic news cluster and event analyzers.

It does not add new data sources, LLM summaries, forecasts, or buy/sell recommendations.

## Section 4: Macro Context

Add evidence rows to `MacroContext`. Each row includes:

- `area`: Rates, USD, Credit, Gold, or Regime.
- `signal`: the computed label.
- `evidence`: the proxy data behind the label, such as `TLT 5D 2.50%`.
- `interpretation`: a concise explanation of what the label means.

The markdown report renders these rows as a table after the existing labels and notes.

## Section 5: Important News Clusters

Add cluster details derived from stored news:

- `source_count`: unique publisher count.
- `why_it_matters`: deterministic explanation based on item count and related assets.
- `manual_read_urls`: source URLs selected for manual reading.

The markdown report renders why the cluster matters, source count, and manual-read links.

## Section 6: Fundamental Events

Add event details:

- `review_type`: deterministic review category.
- `why_it_matters`: deterministic explanation of why the event deserves attention.

The markdown report renders these fields in the event table.

## Compatibility

New dataclass fields use defaults so existing tests and callers remain compatible.

## Testing

Tests should cover:

- Macro analyzer emits evidence rows from proxy returns.
- News cluster analyzer emits source count, why-it-matters text, and manual read URLs.
- Fundamental event analyzer emits review type and why-it-matters text.
- Markdown renders the richer Section 4-6 details.
