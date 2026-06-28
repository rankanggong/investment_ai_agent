# News-Derived Fundamental Events Design

## Goal

Improve section 5 and populate section 6 using stored news headlines, without adding a new API, LLM dependency, or SEC filing pipeline.

## Scope

This version uses existing `news_items` records collected through Google News RSS. It does not scrape article bodies, query SEC EDGAR, call Bedrock, or persist separate event rows.

## Section 5

Keep deterministic news clustering, but make the report output more informative by showing cluster item count alongside topic, related assets, confidence, and representative headlines.

## Section 6

Add a `FundamentalEvent` dataclass and `analyze_fundamental_events(news_items)` analyzer. The analyzer scans headlines with deterministic keyword rules:

- `earnings_release`: earnings, results, quarterly profit, revenue
- `guidance_change`: guidance, outlook, forecast, cuts forecast, raises forecast
- `buyback`: buyback, repurchase
- `dividend_change`: dividend, payout
- `management_change`: CEO, CFO, resigns, appoints
- `regulatory_event`: probe, lawsuit, antitrust, SEC, regulator

The report renders detected events with event type, related asset, confidence, headline, publisher, and URL. If none are found, it renders `No fundamental events detected from stored news.`

## Testing

Tests use synthetic `NewsItem` instances. No network calls are introduced.

