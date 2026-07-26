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

Report-specific portfolio targets, daily investment budget, action sizing, USD
daily spend, and standing GPT questions are configured in
`config/report_profile.json`. Target weights must sum to `1.0`; the target
policy also states the comparison basis and tolerance. The daily budget states
its currency and optional per-action bounds. Unconfigured values remain `N/A`;
the agent does not invent allocation targets, sizing fractions, or spending
assumptions.

CSV imports require these columns:

```text
symbol,date,open,high,low,close,adjusted_close,volume
```

Live collection updates every asset in `config/watchlist.yaml`. To collect only
selected symbols:

```bash
python -m app.main collect prices --yfinance --symbols SPY QQQ
```

Yahoo collection is incremental by default. Symbols with fewer than 200 daily
rows or less than 330 calendar days of history receive a one-year backfill.
Symbols with complete history normally refresh only the latest five trading
days; a stale symbol automatically receives a wider window so missed dates are
filled. Use `--period 1y` to force a full one-year refresh.

Successful symbols are saved even when another symbol fails. Failed symbols are
listed in the command output.

`USD/CNH` is stored under that domain symbol while Yahoo retrieval tries
`CNH=X` first and `USDCNH=X` when the primary code returns no history. The
watchlist also includes the US 10-year Treasury yield (`^TNX`) and US Dollar
Index (`DX-Y.NYB`) so the report can prefer actual macro market levels over ETF
proxies when those histories are available.

The daily report contains:

- independent market, portfolio-decision, and news states with use-specific
  actionability, plus issue-only data quality;
- cost-based portfolio aggregation, configured target gaps, daily budget, and
  USD coverage days;
- state changes since the previous comparable report;
- separate invested-sleeve and total-liquid-asset allocation views with explicit
  cost/balance basis and availability reasons;
- at most ten key market/macro evidence rows, separating 50D/200D medium-term
  trend from 5-day movement and showing drawdown from the 252-day high;
- triggered or near-threshold deterministic rules with 60D absolute-move
  z-score, 20D ATR multiple, and 252D absolute-move percentile;
- separate market risk, portfolio exposure risk, and portfolio data-quality
  risk scores, with single-asset alerts distinct from correlated clusters;
- configured cost-basis factor-tag exposure and an explicit mapping from market
  risk components/clusters to portfolio impact screening scores;
- explicit FX state with USD coverage, latest USD/CNH spot, weighted all-in
  conversion cost basis, and their percentage difference;
  tracked-universe breadth, VIX, and RSP-versus-SPY evidence;
- GPT analysis tasks with stable IDs, `ready`/`degraded`/`blocked` status,
  evidence references, and expected-output contracts;
- deterministic strategy rules with condition-level results, explicit
  `ready`/`blocked`/`waiting_for_condition` action readiness, and mandatory
  human approval for every decision candidate;
- persisted daily decision-state history for comparing readiness, candidate
  actions, rule states, factor exposures, and portfolio impact over time;
  and
- an appendix with full price evidence, account detail, technical bounds, macro
  evidence, and raw price sources.

The generated report is research support only. It does not provide trading advice, buy/sell instructions, or predictions.

## Portfolio Steward

The steward reads one authoritative CSV containing current cash positions,
holding snapshots, and FX conversions. It does not require detailed bank
transactions or PDF statement parsing. Each cash position must explicitly use
`investment_cash`, `investment_source`, `reserved`, `emergency`, or `unknown`
as its `cash_role`; the report never
infers deployability from the account or currency:

```bash
python -m app.main steward init-db
python -m app.main steward import \
  --csv data/steward/templates/steward_state_template.csv
python -m app.main steward report
```

Each row uses `record_type` to select its contract:

- `cash`: account balance, snapshot date, and explicit cash role.
- `holding`: asset quantity, unit cost, currency, and snapshot date.
- `fx`: sold/bought currencies and amounts, conversion date, and fee.

The CSV must contain these columns:

```text
record_type,as_of_date,institution,account_label,currency,cash_balance,cash_role,
symbol,asset_name,quantity,unit_cost,acquired_on,fx_date,sold_currency,
sold_amount,bought_currency,bought_amount,fee_currency,fee_amount,notes
```

Dates use `YYYY-MM-DD`; numbers use a decimal point without thousands
separators. `RMB` and `人民币` are normalized to `CNY`. The import is atomic and
replaces the prior steward state only after every populated row validates.
Cash rows require `cash_role` set to `investment_cash`, `investment_source`,
`reserved`, `emergency`, or `unknown`; the agent never infers cash availability
from an account name. Legacy `investable` and `unclassified` values remain
importable and are normalized to the canonical roles.

Strategy rules live in `config/report_profile.json`. Rules declare an ID,
symbol, candidate action, priority, optional safety-blocking behavior, and typed
conditions. Supported metrics are `drawdown_from_252d_high`,
`vix_level_percentile_252d`, `credit_state`, and
`earnings_revision_negative`. Missing condition evidence blocks that rule; GPT
may explain the computed result but does not create or alter rules.

Rule evaluation and action sizing are separate. A triggered rule produces a
Decision Candidate. A matching `action_sizing` entry can then calculate a
proposed amount as a configured fraction of the Daily Investment Budget,
subject to its optional minimum and maximum. The result always awaits human
approval and never authorizes or executes an order.

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
