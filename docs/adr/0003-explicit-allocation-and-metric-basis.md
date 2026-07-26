# Explicit Allocation and Metric Basis

The daily report exposes two allocation views rather than one ambiguous
"Current Allocation" value:

- Invested Sleeve Allocation uses supplied holding cost converted to the report
  base currency.
- Total Liquid Asset Allocation uses the same holding-cost basis plus supplied
  cash balances. It is unavailable when a cash role or required FX conversion
  is missing.

Neither view is described as market-value allocation.

Standardized price metrics use names that state both subject and window:
`absolute_move_z_score_60d`, `absolute_move_percentile_252d`, and
`drawdown_from_252d_high`. The VIX percentile is separately identified as a
252-day level percentile. Medium-term trend is classified from close relative
to both 50DMA and 200DMA; the 20-session change in 50DMA is supporting evidence,
not a separate classification gate.

FX state uses the latest USD/CNH close as an offshore spot approximation and a
USD-amount-weighted all-in cost basis from supplied CNY-to-USD conversions. The
spot-to-cost-basis difference is descriptive and does not imply an FX action.
