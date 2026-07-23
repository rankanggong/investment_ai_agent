# Investment AI Agent

Local financial data assistant for long-term investment research and personal
portfolio stewardship.

The active workflow is intentionally data-first:

- Market analysis uses stored price history for moves, sector rotation, macro
  context, plan impact, and company price review bounds.
- Personal financial analysis uses one supplied state CSV for cash positions,
  holding snapshots, and FX conversions.
- RSS/news collection and news-derived report sections are currently disabled.
  The existing news schema and implementation remain in the repository so the
  feature can be restored without deleting historical data.

The market workflow is price-only:

```bash
cd /home/ssm-user/investment_ai_agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"

python -m app.main init-db
python -m app.main collect prices --csv path/to/prices.csv
python -m app.main collect prices --yfinance
python -m app.main report daily
```

The daily market report reads holding snapshots from the steward database and
includes them in `Portfolio Holdings`. Cash positions and FX conversions are
not included in the daily market report. Use `--steward-db` to select a
non-default steward database.

CSV imports require these columns:

```text
symbol,date,open,high,low,close,adjusted_close,volume
```

Live collection fetches six months of daily history for every asset in
`config/watchlist.yaml`. To collect only selected symbols:

```bash
python -m app.main collect prices --yfinance --symbols SPY QQQ
```

Successful symbols are saved even when another symbol fails. Failed symbols are
listed in the command output.

The generated report is research support only. It does not provide trading advice, buy/sell instructions, or predictions.

## Portfolio Steward

The steward reads one authoritative CSV containing current cash positions,
holding snapshots, and FX conversions. It does not require detailed bank
transactions or PDF statement parsing:

```bash
python -m app.main steward init-db
python -m app.main steward import \
  --csv data/steward/templates/steward_state_template.csv
python -m app.main steward report
```

Each row uses `record_type` to select its contract:

- `cash`: account balance and snapshot date.
- `holding`: asset quantity, unit cost, currency, and snapshot date.
- `fx`: sold/bought currencies and amounts, conversion date, and fee.

The CSV must contain these columns:

```text
record_type,as_of_date,institution,account_label,currency,cash_balance,
symbol,asset_name,quantity,unit_cost,acquired_on,fx_date,sold_currency,
sold_amount,bought_currency,bought_amount,fee_currency,fee_amount,notes
```

Dates use `YYYY-MM-DD`; numbers use a decimal point without thousands
separators. `RMB` and `人民币` are normalized to `CNY`. The import is atomic and
replaces the prior steward state only after every populated row validates.

## Amazon Bedrock

The reusable LLM client uses Amazon Bedrock's Converse API. It defaults to
`qwen.qwen3-32b-v1:0`; override it with
`FINANCE_AGENT_BEDROCK_MODEL_ID`.

Set `AWS_REGION` to a region where the selected model is available and enabled.
Credentials use boto3's standard AWS credential provider chain, such as
environment variables, shared AWS configuration, or an IAM role.

```python
from app.llm import BedrockClient

client = BedrockClient()
text = client.converse(
    [{"role": "user", "content": "Summarize these supplied market facts."}],
    system_prompt="Do not infer facts that were not supplied.",
)
```
