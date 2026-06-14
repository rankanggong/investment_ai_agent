# Investment AI Agent

Local financial research assistant for long-term investment research.

Phase 1 implements a price-only MVP:

```bash
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
