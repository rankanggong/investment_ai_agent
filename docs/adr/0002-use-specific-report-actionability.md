# Separate Report Actionability by Use

The daily report exposes six capability states: market analysis, macro analysis,
portfolio analysis, investment action, FX analysis, and news analysis. It does
not collapse a missing optional input into an overall quality gate. Overall data
quality is blocked only by unusable core prices, widespread calculation failure,
time-alignment failure, or schema failure.

Portfolio exposure risk and portfolio data-quality risk remain separate. A stale
snapshot or unknown cash role blocks decision readiness without being presented
as investment risk. Downstream GPT tasks carry stable IDs and
`ready`/`degraded`/`blocked` status derived from the capability they require.
