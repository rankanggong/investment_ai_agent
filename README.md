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

The dormant news path is fail-closed: query symbols are collection provenance,
not entity links. Articles must pass ticker/name entity linking before they can
be clustered; ETF, company, index, and commodity events use separate schemas
and are deduplicated at the event level. If entity precision is below 80%, news
and fundamental scores are null and portfolio action is unavailable.

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

The daily market report reads cash positions, holding snapshots, and FX
conversions from the steward database. Its main body is a compact market-state
view; full account detail is kept in the appendix. Use `--steward-db` to select
a non-default steward database.

Report-specific portfolio targets, daily investment budget, USD daily spend,
and standing GPT questions are configured in `config/report_profile.json`.
Target allocations must sum to `1.0`. Unconfigured values remain `N/A`; the
agent does not invent allocation targets or spending assumptions.

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

`USD/CNH` is stored under that domain symbol while Yahoo retrieval tries
`CNH=X` first and `USDCNH=X` when the primary code returns no history. The
watchlist also includes the US 10-year Treasury yield (`^TNX`) and US Dollar
Index (`DX-Y.NYB`) so the report can prefer actual macro market levels over ETF
proxies when those histories are available.

The daily report contains:

- executive state and issue-only data quality;
- cost-based portfolio aggregation, configured target gaps, daily budget, and
  USD coverage days;
- state changes since the previous comparable report;
- at most ten key market/macro evidence rows, separating 20-day structure from
  5-day countertrend movement;
- triggered or near-threshold deterministic rules with an explained risk score;
- GPT analysis questions; and
- an appendix with full price evidence, account detail, technical bounds, macro
  evidence, and raw price sources.

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
