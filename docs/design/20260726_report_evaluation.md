# Daily Market State Report Improvement Plan

Version: v1.0
Target: Coding Agent Implementation Specification

## 1. Background

当前 Daily Market State Report 已经完成：

- 市场价格数据采集
- 技术指标计算
- 市场风险评分
- 组合状态分析
- 数据质量检查
- GPT Analysis Tasks 输出

当前版本已经具备作为 Agent → GPT 分析接口的基础。

下一阶段目标：

从：

"Market Analysis Report"

升级为：

"Investment Decision State Layer"

核心原则：

1. 不让 GPT 猜测缺失信息
2. 明确区分事实、计算状态、策略判断
3. 支持未来接入用户投资规则
4. 支持自动判断哪些任务可以交给 GPT
5. 避免错误状态导致错误投资建议


---

# 2. Current Problems Summary

## P0 Problems

必须优先修复。

---

## Problem 1: Data Quality 状态过于粗粒度

### Current

Example:

Overall: blocked

原因：

- News blocked
- Portfolio stale
- Cash role missing
- Technical insufficient


问题：

当前 blocked 会导致 GPT 误认为整个报告不可使用。

实际上：

| Module | Status |
|-|-|
| Market Price Analysis | Available |
| Macro Analysis | Available |
| Portfolio Action | Blocked |
| News Analysis | Blocked |
| FX Decision | Degraded |


### Required Change

拆分 Data Quality。

新增：

```yaml
data_quality:

  overall:
    status: degraded


  capabilities:

    market_analysis:
      status: available

    macro_analysis:
      status: available

    portfolio_analysis:
      status: limited

    investment_action:
      status: blocked

    fx_analysis:
      status: degraded

    news_analysis:
      status: blocked
Rules
只有以下情况：
核心价格数据不可用
大量资产计算失败
时间无法对齐
schema 错误
才允许：
overall.status = blocked
Problem 2: Portfolio Risk 定义错误
Current
Example:
Portfolio risk: 52/100 elevated
但是：
25 points:
stale portfolio snapshot

20 points:
unclassified cash
这些不是投资风险。
它们代表：
"无法判断投资组合状态"
Required Change
拆分：
portfolio_state:

  exposure_risk:
    score: 7


  data_quality_risk:
    score: 45


  decision_readiness:
    status: blocked
Rename
不要：
Portfolio Risk
改：
Portfolio Decision Uncertainty
或者：
Portfolio Readiness Risk
Problem 3: Allocation Basis 不够明确
Current
Current Allocation:
QQQ 64.52%
VOO 19.71%
Gold 15.77%
实际含义：
percentage of invested holding cost
不是：
total liquid asset allocation
Required Change
同时生成两个维度。
Invested Sleeve Allocation
invested_allocation:

  QQQ:
    weight: 64.52%

  VOO:
    weight: 19.71%

  Gold:
    weight: 15.77%
Total Liquid Asset Allocation
liquid_asset_allocation:

  QQQ:
    weight: unknown

  VOO:
    weight: unknown

  Gold:
    weight: unknown

  Cash:
    weight: unknown


  status:
    unavailable

  reason:
    cash_role_not_configured
Problem 4: Cash Role Management
Current
所有现金：
unclassified
导致：
investable cash = 0
reserved cash = 0
Required Change
增加 cash role。
Schema:
cash_positions:


- account:
    BOA_USD

  currency:
    USD

  role:
    reserved


- account:
    ICBC_USD

  currency:
    USD

  role:
    investment_cash


- account:
    CMB_RMB

  currency:
    CNY

  role:
    investment_source
Allowed Roles:
investment_cash
investment_source
reserved
emergency
unknown
Problem 5: GPT Task 生成需要支持状态
Current
所有 Task 默认生成。
问题：
部分任务依赖缺失数据。
Example:
Question:
"最大配置缺口是什么"
但是：
target allocation missing
GPT 不应该回答。
Required Change
Task 增加状态。
Schema:

gpt_task:


id:
  evaluate_allocation_gap


status:
  blocked


blocked_reason:

 - target_allocation_missing
 - daily_budget_missing


Task Status:
ready
degraded
blocked
3. Risk Model Improvements
Problem 6: Risk Score 需要进一步拆分
Current:
Market Risk
Portfolio Risk
Required:

risk:

 market:

   total_score: 12


   components:

     unusual_moves:
       score: 10


     breadth:
       score: 2


     volatility:
       score: 0


     macro:
       score: 0



 portfolio:

   exposure:
     score: 7


   data_quality:
     score:45


Problem 7: Risk Cluster 语义优化
Current
Example:
mega_cap_companies:
  AAPL
问题：
单资产不是 cluster。
Required
拆分：

unusual_moves:


 single_asset_alerts:

   - AAPL
   - XLRE



 correlated_clusters:


   - name:
       semiconductor


     assets:

       - NVDA
       - SMH
       - SOXX


规则：
Cluster:
minimum assets >= 2
否则：
single_asset_alert
4. Technical Indicator Improvements
Problem 8: Trend Definition Need Documentation
Current:
medium_term_uptrend
medium_term_downtrend
mixed
但是没有定义。
Required
Add:

trend_model:


medium_term:


 inputs:

   - close_vs_50dma
   - close_vs_200dma
   - dma_slope


Classification:
uptrend:

 close > 50DMA
 AND
 close > 200DMA


downtrend:

 close < 50DMA
 AND
 close < 200DMA


mixed:

 otherwise
Problem 9: z-score Definition
Current:
z-score
含义不明确。
Required
Rename:
Current:
z-score
Change:
return_z_score
or:
absolute_move_z_score
depending on implementation.
Document:

metric_definition:


return_z_score:

 formula:

   (return - mean_return)
   /
   std_return

Problem 10: Drawdown Definition
Current:
Drawdown
Ambiguous.
Required:

drawdown:


window:

252


basis:

rolling_high


formula:

(current_price / rolling_high)-1

Output:
Drawdown from 252D high
Problem 11: Percentile Naming
Current:
Percentile
Need split:

percentile:


price_move_percentile:
  

volatility_percentile:


level_percentile:


Example:
VIX level percentile
VIX move percentile
Do not mix.
5. Macro State Improvements
Problem 12: Macro Regime Too Generic
Current:
mixed
Often loses information。
Required
Generate:

macro_regime:


rates:

  state:
    tightening_pressure


usd:

  state:
    neutral


credit:

  state:
    stable


overall:

  label:
    rotation_under_rate_pressure

Possible Labels:
risk_on
risk_off
rotation_under_rate_pressure
growth_slowdown
inflation_pressure
mixed
6. Portfolio Strategy Layer
当前缺少：
State → Action Rules
不要让 GPT 自由创造策略。
增加：

strategy_rules:


qqq:


 base_investment:


   enabled:
     true



 manual_add:


   level_1:


     conditions:

       - drawdown_from_high >= 8%

       - credit != stressed



   level_2:


     conditions:

       - drawdown_from_high >= 12%

       - vix_percentile > 80



 pause:


     conditions:

       - earnings_revision_negative

GPT 只判断：
Rule triggered?
而不是重新设计策略。
7. FX Module Improvements
Required
增加：

fx_state:


usd_balance:


usd_required_daily:


coverage_days:



spot:


usd_cnh:


cost_basis:


difference_pct:

Example:
USD/CNH spot:
6.77


Average conversion:
6.7938


Difference:
-0.35%

8. Executive Summary Rewrite
Current:
Market state is review_required
Too generic。
Required:
Example:
Market:

- Broad market stable
- Growth leadership weakening
- Rate pressure remains


Portfolio:

- Decision blocked
- Cash roles missing
- Target allocation missing


Actionability:

- Market analysis available
- Investment action unavailable

9. Machine Readable State
Current:
Need expansion.
Required:

{


"market_state":

{

 "risk_level":"low",

 "regime":"rotation_under_rate_pressure"

},


"portfolio_state":

{

 "decision_readiness":"blocked",

 "data_quality":"degraded"

},


"capabilities":

{

 "market_analysis":true,

 "portfolio_action":false,

 "fx_action":false

},


"gpt_tasks":

[

"task_id"

]

}

10. Implementation Priority
Phase 1 (Required)
Data quality capability model
Portfolio uncertainty split
Cash roles
GPT task status
Risk cluster correction
Phase 2
Trend model documentation
Indicator naming cleanup
FX state calculation
Portfolio aggregation
Phase 3
Strategy rules engine
Automatic action readiness
Historical decision tracking
Acceptance Criteria
完成后：
GPT should be able to answer:

"今天市场是否危险？"
without confusing:
market risk
and
portfolio data quality.

"我是否应该加仓？"
should return:
ready
blocked
waiting for condition

"为什么风险评分变化？"
should trace:
score
↓
component
↓
evidence
↓
rule

"当前报告哪些部分可信？"
should be directly available from capability state.
Final Goal
The system should evolve from:
Market Report Generator
to:
Investment Decision State Engine
Architecture:
Data
↓
State
↓
Rules
↓
GPT Reasoning
↓
Decision Candidate
↓
Human Approval
GPT should not replace deterministic logic.
GPT should reason on top of verified state.