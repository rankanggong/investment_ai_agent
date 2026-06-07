# Investment AI Agent

Local financial research assistant for long-term investment research.

Phase 1 implements a price-only MVP:

```bash
python -m app.main init-db
python -m app.main collect prices --csv path/to/prices.csv
python -m app.main report daily
```

CSV imports require these columns:

```text
symbol,date,open,high,low,close,adjusted_close,volume
```

The generated report is research support only. It does not provide trading advice, buy/sell instructions, or predictions.

