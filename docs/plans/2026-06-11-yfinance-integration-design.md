# yfinance Price Collection Design

## Goal

Add live daily-price collection through yfinance while preserving the existing CSV import workflow.

## Interface

The existing `collect prices` command accepts exactly one input mode:

```bash
finance-agent collect prices --csv path/to/prices.csv
finance-agent collect prices --yfinance
finance-agent collect prices --yfinance --symbols SPY QQQ
```

Live collection uses every symbol in `config/watchlist.yaml` unless `--symbols` is supplied. It fetches six months of daily history by default.

## Architecture

`app/collectors/yfinance_price_collector.py` owns the yfinance dependency and normalizes provider rows into existing `PriceBar` values. Symbols are downloaded independently so unsupported or failed symbols do not prevent successful symbols from being saved.

The collector returns successful bars and a list of failed symbols. The CLI loads the watchlist, invokes the collector, upserts successful bars through `PriceRepository`, and reports both the imported row count and failures.

## Error Handling

An exception or empty result for one symbol marks only that symbol as failed. The command completes after saving all successful results. CSV import behavior remains unchanged.

## Testing

Unit tests inject a fake ticker-history function, avoiding network access while covering row normalization, empty results, exceptions, and partial success. CLI tests cover the mutually exclusive input modes and yfinance defaults.

