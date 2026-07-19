# Investment AI Agent

Local financial data assistant for long-term investment research and personal
portfolio stewardship.

The active workflow is intentionally data-first:

- Market analysis uses stored price history for moves, sector rotation, macro
  context, plan impact, and company price review bounds.
- Personal financial analysis uses locally imported account statements for cash,
  transfer, and FX review.
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

The independent steward imports supported bank/payment statements from a local
folder and writes a cash, transfer, and FX review report:

```bash
python -m app.main steward init-db
python -m app.main steward import --inbox data/steward/inbox
python -m app.main steward report
```

Register both sides of a possible internal transfer as owned accounts, using the
institution and account labels shown in the report:

```bash
python -m app.main steward account set \
  --institution cmb --account bank-label --currency CNY \
  --ownership owned --role bank
python -m app.main steward account set \
  --institution broker --account cash-label --currency CNY \
  --ownership owned --role brokerage
```

Generate the report again to see transfer candidates. Confirm or reject a pair
using its statement transaction IDs:

```bash
python -m app.main steward transfer confirm --outgoing-id 10 --incoming-id 20
python -m app.main steward transfer reject --outgoing-id 30 --incoming-id 40
```

Only confirmed transfers are excluded from external household cashflow.
Unconfirmed candidates remain included and are shown for manual review.

### Manual Holding Import

Holdings that are not available from a statement parser can be supplied as CSV:

```bash
python -m app.main steward holding import --csv path/to/holdings.csv
```

The CSV must contain these columns:

```text
institution,account_label,symbol,name,quantity,currency,unit_cost,acquired_on
```

`acquired_on` uses `YYYY-MM-DD`. Importing the same institution, account,
symbol, and acquisition date again updates that holding, so corrected files can
be re-imported safely. Currency names such as `美元` and `人民币` are normalized
to `USD` and `CNY`.

For each USD holding, the importer looks through already imported cash
transactions for a positive USD entry marked as an FX conversion and dated no
later than the holding acquisition. It prefers the same institution/account,
then the same institution, then the nearest date. The linked statement
transaction ID is stored with the holding for audit. If no eligible transaction
exists, the holding is still imported and the command prints a warning.

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
