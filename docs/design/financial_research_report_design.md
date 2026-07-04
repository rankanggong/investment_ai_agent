# Financial Research Report v2 设计文档

> 目标：规划本地金融 agent 的核心输出物：Market Research Report。  
> 当前重点：先忽略 Discord、多人使用、频道、推送、订阅、slash command 等分发问题，只设计 report 本身。  
> 定位：Market Research Assistant，不是 Trading Bot，不提供买卖指令。  
> 核心原则：数据先行、事实与解释分离、低噪音、可复盘、可扩展。

---

## 0. 文档状态与使用方式

这份文档现在作为 **report contract** 使用，而不是早期 MVP 草案。

当前代码已经实现了 price signal、sector rotation、macro proxy、news cluster、fundamental event、daily signal summary、data coverage、plan impact、popular company price bounds 等报告模块。因此本文档的重点应从“第一版要有哪些 section”调整为：

```text
1. 每个 section 的责任边界是什么？
2. 哪些内容必须由 deterministic analyzer 计算？
3. 哪些解释可以由模板或 LLM 生成？
4. 每个 signal 必须带哪些证据、置信度和数据覆盖说明？
5. 什么内容不能出现在报告里？
```

本文档不直接替代具体实现计划。新增功能仍应单独写到 `docs/plans/` 或 `docs/superpowers/plans/`。

---

## 1. Report 的核心定位

这个系统的核心产品不是“推送 bot”，而是稳定产出的金融研究报告。

Report 不应该只是新闻摘要，而应该回答：

```text
1. 今天市场整体是 risk-on 还是 risk-off？
2. 哪些资产 / 板块明显强或弱？
3. 这些变化可能由什么驱动？
4. 哪些变化可能和基本面有关，哪些只是价格噪音？
5. 对 SPY / QQQ / GLD / TLT / USD/CNY 等核心观察有什么影响？
6. 接下来应该继续看什么数据、事件或确认信号？
```

Report 不应该重点回答：

```text
今天该买什么？
明天会涨还是跌？
哪个股票一定有机会？
是否应该立刻加仓？
```

推荐输出方式：

```text
发生了什么
可能为什么
证据是什么
不确定性在哪里
接下来值得观察什么
```

避免输出方式：

```text
强烈看涨
马上买入
确定反转
抄底机会
稳赚
梭哈
```

---

## 2. Report 分层设计

建议把报告体系分成三层：

```text
Daily Report：今天发生了什么
Weekly Report：这周结构上有什么变化
Special Report：某个资产 / 主题为什么值得关注
```

第一阶段重点做 **Daily Report**，因为它最容易验证完整 pipeline：

```text
价格数据
↓
指标计算
↓
板块分析
↓
异动检测
↓
宏观代理判断
↓
报告生成
```

---

## 3. Daily Report 当前结构

当前 report 已经不是 price-only MVP。设计上应以当前 Markdown writer 的输出结构作为 canonical contract：

```markdown
# Daily Market Brief - YYYY-MM-DD

## 0. What Matters Today
## Data Coverage
## 1. Market Overview
## 2. Biggest Moves
## 3. Sector Rotation
## 4. Macro Context
## 5. Important News Clusters
## 6. Fundamental Events
## 7. Impact On My Plan
## 8. What To Read Manually
## 9. Popular Company Price Bounds
```

设计含义：

```text
What Matters Today = triage layer，告诉用户今天是否值得看
Data Coverage = trust layer，解释哪些 quiet / unknown 来自缺数据
Market Overview / Biggest Moves / Sector Rotation = price-derived facts
Macro Context = ETF proxy macro interpretation
News / Fundamentals = event layer，不直接覆盖价格结论
Impact On My Plan / Price Bounds = personal research mapping，不是交易指令
Manual Reading = escalation layer，只列值得人工阅读的原始材料
```

早期 MVP 结构仍可作为历史参考，但不再作为实现优先级。后续优化应减少重复、提高 signal quality，而不是继续增加 section 数量。

---

## 4. Section 设计

---

## 4.1 What Matters Today

### 目标

让用户只看这一段，也能判断今天是否需要继续读完整报告。

这个 section 不是传统 Executive Summary，而是 triage layer。

### 内容要求

- 明确状态：`review_required` / `monitor` / `no_material_signal`
- 给出 3-5 个 driver
- 给出一句 reason
- 不给买卖建议
- 明确哪些信号来自价格、板块、宏观、新闻、基本面事件
- 输入必须来自结构化 analysis result，不由 LLM 自行判断

### 示例

```markdown
## 0. What Matters Today

Status: monitor

Drivers:
- Price: no unusual moves
- Sector rotation: risk-on score 0.42
- Macro: mixed
- News: 2 important clusters
- Fundamental events: none detected

Reason: Monitor because sector rotation and news clusters crossed thresholds.
```

### 输入数据示例

```json
{
  "status": "monitor",
  "drivers": [
    "Price: no unusual moves",
    "Sector rotation: risk-on score 0.42",
    "Macro: mixed",
    "News: 2 important clusters",
    "Fundamental events: none detected"
  ],
  "reason": "Monitor because sector rotation and news clusters crossed thresholds."
}
```

### 后续增强

可以在保持 deterministic status 的基础上，增加一段 2-3 bullet 的 natural-language summary。但这段必须由 analyzer output 生成，不能引入新事实。

---

## 4.1.1 Data Coverage

### 目标

解释 report 中的 `unknown`、`deferred`、`no signal` 到底是因为真的没有信号，还是因为数据不足。

### 内容要求

- 放在 `What Matters Today` 后、Section 1 前
- 显示每类数据的 availability
- 对可能影响解读的缺口给出 impact note
- 不把缺数据解释成市场结论

### 示例

```markdown
## Data Coverage

| Category | Item | Status | Rows | Latest | Detail |
|---|---|---|---:|---|---|
| Macro | UUP | missing | 0 | N/A | Needs at least 6 price rows for 5D macro context. |

Impact:
- Section 4 may be unknown because UUP is missing.
```

---

## 4.2 Market Overview

### 目标

展示核心资产的基础状态。

### 建议资产

```text
SPY
QQQ
IWM
GLD
TLT
UUP / DXY
HYG
LQD
```

### 表格模板

```markdown
## 1. Market Overview

| Asset | 1D | 5D | 20D | Volume vs 20D | Note |
|---|---:|---:|---:|---:|---|
| SPY | +0.4% | +1.2% | +3.8% | 0.9x | Broad market stable |
| QQQ | +0.9% | +2.4% | +5.6% | 1.2x | Growth leading |
| GLD | -0.3% | +0.5% | +4.1% | 1.0x | Gold consolidating |
| TLT | +0.2% | -0.8% | -2.1% | 0.8x | Rates pressure unclear |
| UUP | +0.1% | +0.6% | +1.4% | 1.1x | Dollar stable |
```

### 生成原则

这个部分主要是事实展示，不需要太多解释。

涨跌幅、成交量比例、相对强弱都应该由代码计算，不由 LLM 计算。当前 writer 已输出 1D / 5D / 20D 和 note；后续可以补回 `Volume vs 20D`，但不应在这个 section 加长解释段落。

---

## 4.3 Asset Class Overview

### 目标

把核心资产分成资产类别，给出更高层的 market regime 判断。

### 当前设计决策

暂时不作为独立 section 实现。

原因：

```text
Equities / Bonds / Gold / USD / Credit 的高层判断已经分布在：
- Market Overview 的核心资产事实表
- Macro Context 的 rates / USD / credit / gold / regime
- What Matters Today 的 triage driver
```

如果单独加入 Asset Class Overview，容易和 Macro Context 重复。更好的做法是先把 `MacroContext` 的 evidence rows 做扎实，再考虑是否需要一个更短的 asset-class summary。

### 资产类别

```text
Equities
Bonds
Gold
USD
Credit
Crypto，可选
Commodities，可选
```

### 示例

```markdown
## 2. Asset Class Overview

**Equities:** US equities were positive, with growth outperforming broad-market exposure.

**Bonds:** Long-duration bonds were stable. There was no strong duration-led risk-off signal.

**Gold:** Gold did not confirm a strong breakout today. The move was mostly neutral relative to USD and rates.

**USD:** The dollar was stable, reducing directional pressure on gold and international assets.

**Credit:** Credit proxies did not show obvious stress.
```

### 可输出 regime

```text
risk_on
risk_off
mixed
defensive_rotation
growth_led
rates_driven
commodity_led
low_signal
```

---

## 4.4 Sector Rotation

### 目标

识别市场内部结构变化。  
这是 report 的核心价值之一。

### 建议板块 ETF

```text
XLK  Technology
XLC  Communication Services
XLF  Financials
XLE  Energy
XLV  Healthcare
XLY  Consumer Discretionary
XLP  Consumer Staples
XLU  Utilities
XLI  Industrials
XLRE Real Estate
XLB  Materials
SOXX Semiconductors
SMH  Semiconductors
```

### 表格模板

```markdown
## 3. Sector Rotation

| Sector | ETF | 1D | 5D | 20D | Relative to SPY | Comment |
|---|---|---:|---:|---:|---:|---|
| Semiconductors | SOXX | +2.8% | +5.4% | +9.2% | +2.4% | Strong leadership |
| Technology | XLK | +1.2% | +3.1% | +6.7% | +0.8% | Growth support |
| Energy | XLE | -1.9% | -3.4% | -2.2% | -2.3% | Weak commodity-sensitive sector |
| Utilities | XLU | -0.5% | -1.1% | +0.4% | -0.9% | Defensive lagging |
```

### 解释模板

```markdown
**Interpretation**

Sector leadership was concentrated in growth and semiconductors. Defensive sectors lagged, which suggests the move was not primarily risk-off. Energy weakness appears isolated rather than broad market stress.
```

### 初版规则

```text
strong sector = 1D relative to SPY > +1%
weak sector = 1D relative to SPY < -1%
leadership confirmed = 1D, 5D, 20D 都强
short-term bounce = 1D 强但 20D 弱
sector pressure = 1D, 5D 都弱
```

---

## 4.5 Biggest Moves

### 目标

只处理值得注意的异常波动，不列所有涨跌。

### 触发条件

```text
超过波动阈值的资产
明显放量的资产
相对 SPY / QQQ 异常强弱的板块
黄金 / 美元 / 债券之间出现明显联动
```

### 表格模板

```markdown
## 4. Biggest Moves

| Asset | Move | Trigger Type | Possible Driver | Confidence |
|---|---:|---|---|---|
| SOXX | +2.8% | Relative strength | AI / semiconductor risk appetite | Medium |
| XLE | -1.9% | Sector weakness | Energy-specific pressure | Low-Medium |
| GLD | +1.6% | Gold watch | USD weakness and lower yields | Medium |
```

### 详情模板

```markdown
### SOXX

**Observed:** SOXX outperformed SPY and QQQ, with volume above recent average.

**Possible drivers:**
1. Stronger semiconductor risk appetite.
2. AI infrastructure-related news cluster.
3. Broad technology leadership.

**Uncertainty:** The move is price-confirmed, but not necessarily a confirmed fundamental change.
```

### 输出必须区分

```text
price_confirmed
volume_confirmed
relative_strength_confirmed
news_supported
macro_supported
fundamental_confirmed
```

不要把价格波动直接写成基本面变化。

---

## 4.6 Macro Context

### 目标

解释今天市场是否受宏观驱动。

### 第一版代理指标

如果还没有正式宏观 API，可以先用 ETF 代理：

```text
TLT = long-duration bond proxy
UUP = dollar proxy
GLD = gold proxy
HYG / LQD = credit risk proxy
SPY / QQQ / IWM = equity risk appetite proxy
```

### 后续正式指标

```text
10Y yield
2Y yield
10Y real yield
DXY
CPI
PCE
Fed Funds Rate
Fed expectation
Yield curve
```

### 示例

```markdown
## 5. Macro Context

**Rates:** Long-duration bonds were stable today, suggesting rates were not the dominant driver of equity performance.

**USD:** The dollar was stable, so currency pressure on gold and international assets was limited.

**Inflation / Fed:** No major inflation or Fed event changed the macro backdrop today.

**Market regime:** The day looked more growth-led than macro-shock-driven.
```

---

## 4.7 Gold / USD / Rates Watch

### 目标

单独跟踪黄金、美元、利率之间的关系。  
这是当前系统的重点专题之一。

### 当前设计决策

第一阶段不单独新增一个 top-level section，而是放在 `## 4. Macro Context` 内作为 Gold / USD / Rates 的 evidence rows 和 notes。

原因：

```text
GLD / UUP / TLT 的关系本质上是 macro proxy context。
单独拆成 section 会和 Macro Context 重复。
如果黄金成为当天主线，What Matters Today 应把它提升为 driver。
如果只是一般状态，保留在 Macro Context 中即可。
```

后续可以增加一个 `gold_signal_state` 字段，但它仍应由 macro / gold analyzer 产出，再由 report writer 渲染。

### 核心观察对象

```text
GLD / IAU
UUP / DXY
TLT
10Y yield
10Y real yield
GDX，可选
Fed expectation，可后置
ETF flows，可后置
央行购金新闻，可后置
```

### 表格模板

```markdown
### Gold / USD / Rates Watch

| Indicator | Move | Interpretation |
|---|---:|---|
| GLD | +1.4% | Gold strengthened |
| UUP | -0.5% | Weaker dollar supportive for gold |
| TLT | +0.8% | Lower yield pressure may support gold |
| GDX | +2.1% | Gold miners confirmed gold strength |
```

### 解释模板

```markdown
**Interpretation**

Gold strength was supported by a weaker dollar and firmer long-duration bonds. This looks more macro-driven than geopolitical-news-driven based on available evidence.

**What would strengthen the signal**
- GLD continues outperforming while UUP weakens.
- TLT rises or real yields fall.
- GDX confirms the move.
- Gold-related ETF flows improve.
```

### Gold signal state

```text
gold_neutral
gold_strengthening
gold_macro_supported
gold_usd_headwind
gold_rate_headwind
gold_breakout_watch
gold_pullback_watch
```

### 输出边界

不要写：

```text
该加仓
现在买
马上抄底
```

可以写：

```text
黄金信号增强
黄金进入更值得观察的状态
黄金上涨但宏观证据不足
黄金缺少确认
```

---

## 4.8 News & Event Clusters

### 目标

将新闻从“标题列表”变成“事件聚类”。

第一阶段如果还没有新闻数据，可以暂缓。  
等接入新闻后，不建议直接列几十条标题，而应聚类总结。

### 模板

```markdown
## 7. News & Event Clusters

### Cluster 1: Semiconductor demand and AI infrastructure

**Related assets:** SOXX, SMH, QQQ, XLK  
**Summary:** Several news items pointed to continued interest in AI infrastructure and semiconductor demand.  
**Market impact:** Supportive for semiconductor leadership today.  
**Confidence:** Medium  
**Evidence:** 3 related news items

### Cluster 2: Energy weakness

**Related assets:** XLE  
**Summary:** Energy underperformed, but current evidence does not clearly identify a single fundamental driver.  
**Confidence:** Low
```

### 结构化输出

```json
{
  "topic": "Semiconductor demand and AI infrastructure",
  "related_assets": ["SOXX", "SMH", "QQQ", "XLK"],
  "event_type": "sector",
  "summary": "...",
  "market_impact": "...",
  "confidence": "medium",
  "source_count": 3
}
```

---

## 4.9 Fundamentals Watch

### 目标

提醒是否出现真正可能影响基本面的事件。

### 关注事件

```text
earnings_release
guidance_change
SEC 8-K
10-Q / 10-K
management_change
lawsuit / regulatory_event
buyback / dividend
M&A
insider_transaction
```

### 无事件模板

```markdown
## 8. Fundamentals Watch

No major fundamental events were detected for the core watchlist today.

Pending:
- Upcoming earnings: NVDA, MSFT
- Filing watch: no new 8-K detected
```

### 有事件模板

```markdown
### AAPL — Earnings Release

**Event:** Quarterly earnings released.  
**Initial read:** Revenue growth was stable, but margin commentary needs further review.  
**Potential impact:** Moderate.  
**Needs manual reading:** Management guidance and segment-level performance.
```

### 注意

这个模块不要强行每日都有内容。没有重大事件时就明确写没有。

---

## 4.10 Watchlist Impact

### 目标

把市场变化映射到长期关注主题，而不是给买卖建议。

### 关注主题

```text
SPY / QQQ 长期配置
黄金加仓观察
USD/CNY 换汇节奏
TLT / 利率变化
现金拖累
房贷机会成本，可放周报
```

### 模板

```markdown
## 9. Watchlist Impact

### SPY / QQQ

QQQ outperformed SPY, indicating growth leadership. This supports the current view that technology remains the primary market driver, but concentration risk should still be watched.

### Gold

Gold did not provide a strong new signal today. The current setup remains watchful rather than confirmed.

### USD / CNY

No strong USD move was detected today. No clear new signal for FX timing.

### Bonds / Rates

TLT was stable. Rate pressure did not materially change the equity/gold setup today.
```

### Impact level

```text
no_change
watch_more_closely
signal_strengthened
signal_weakened
manual_review_needed
```

### JSON 示例

```json
{
  "topic": "gold_accumulation_watch",
  "impact_level": "watch_more_closely",
  "reason": "GLD rose while UUP weakened and TLT strengthened",
  "confidence": "medium"
}
```

---

## 4.11 What To Watch Next

### 目标

把 report 从“总结过去”变成“指导下一步观察”。

### 当前状态

这是当前 live report 中最值得补强但尚未作为独立 section 稳定输出的部分。

建议下一步不要让 LLM 自由生成观察项，而是先由 analyzer / template 生成：

```text
price unusual move -> watch continuation / reversal / volume confirmation
sector rotation -> watch breadth and whether leadership broadens
macro context -> watch proxy confirmation from TLT / UUP / HYG / LQD / GLD
news cluster -> watch whether price confirms or fades the event
fundamental event -> watch source filing / earnings transcript / guidance detail
data coverage gap -> watch missing source after next collection run
```

每个观察项应避免操作建议，只描述需要验证的条件。

### 模板

```markdown
## 10. What To Watch Next

1. Whether semiconductor leadership broadens beyond SOXX / SMH into the broader QQQ.
2. Whether gold can continue outperforming if the dollar weakens further.
3. Whether energy weakness remains isolated or spreads into broader cyclicals.
4. Upcoming inflation / Fed-related data that may affect rates and gold.
5. Whether defensive sectors continue lagging, confirming risk-on tone.
```

### 原则

只写观察项，不写操作建议。

---

## 5. Report 状态标签设计

为了让 report 稳定，不要每次都让 LLM 自由发挥。  
Analyzer 应先产出状态标签，Report Writer 再把状态标签转换成自然语言。

### 5.0 Signal Contract

任何非纯事实的 report conclusion 都应尽量满足以下 contract：

```json
{
  "subject": "SOXX",
  "observed_fact": "SOXX outperformed SPY over 5D",
  "trigger_type": "relative_strength",
  "evidence_type": [
    "price_confirmed",
    "relative_strength_confirmed"
  ],
  "interpretation": "Semiconductor leadership strengthened versus broad market.",
  "confidence": "medium",
  "data_coverage": "available",
  "uncertainty": "No confirmed fundamental event is linked to the move.",
  "watch_next": "Whether leadership broadens into XLK and QQQ.",
  "invalidation": "SOXX gives back relative outperformance while QQQ remains flat."
}
```

最小字段：

```text
observed_fact
trigger_type
evidence_type
confidence
uncertainty
watch_next
```

这个 contract 的目标不是让每个 section 都变长，而是防止 report 把“价格变化”直接写成“基本面变化”。

### Evidence type

```text
price_confirmed
volume_confirmed
relative_strength_confirmed
macro_supported
news_supported
fundamental_confirmed
data_limited
manual_review_required
```

### Trigger type

```text
absolute_move
relative_strength
relative_weakness
volume_spike
sector_rotation
macro_proxy_shift
news_cluster
fundamental_event
price_bound_review
data_gap
```

### Data coverage state

```text
available
insufficient
missing
stale
not_applicable
```

Report writer 可以只渲染其中一部分字段，但 analyzer 层应尽量保留这些结构化信息，便于以后生成 HTML、dashboard、weekly report 和回测复盘。

### 5.1 Market regime

```text
risk_on
risk_off
mixed
growth_led
defensive_rotation
rates_driven
commodity_led
macro_event_driven
low_signal
```

### 5.2 Sector state

```text
broad_strength
narrow_growth_leadership
defensive_leadership
cyclical_leadership
energy_pressure
semi_leadership
rotation_unclear
```

### 5.3 Gold state

```text
gold_neutral
gold_strengthening
gold_macro_supported
gold_usd_headwind
gold_rate_headwind
gold_breakout_watch
gold_pullback_watch
```

### 5.4 Signal confidence

```text
low
medium
high
```

### 5.5 Fundamental impact

```text
none_detected
minor
moderate
material
unknown_needs_review
```

---

## 6. Report 生成数据结构

Report Writer 不应该直接读 CSV，而应该读一个结构化 JSON。  
CSV 应先经过 analyzer，生成 report context。

### 示例

```json
{
  "report_date": "2026-05-15",
  "daily_signal_summary": {
    "status": "monitor",
    "drivers": [
      "Price: 1 unusual move",
      "Sector rotation: risk-on score 0.42",
      "Macro: mixed",
      "News: no important clusters",
      "Fundamental events: none detected"
    ],
    "reason": "Monitor because price and sector signals crossed thresholds."
  },
  "data_coverage": {
    "rows": [
      {
        "category": "Macro",
        "item": "UUP",
        "status": "available",
        "rows": 120,
        "latest": "2026-05-15",
        "detail": "Enough data for 5D macro context."
      }
    ],
    "impacts": []
  },
  "market_overview": {
    "SPY": {
      "return_1d": 0.004,
      "return_5d": 0.012,
      "return_20d": 0.038,
      "volume_ratio_20d": 0.9
    },
    "QQQ": {
      "return_1d": 0.009,
      "return_5d": 0.024,
      "return_20d": 0.056,
      "volume_ratio_20d": 1.2
    }
  },
  "sector_rotation": {
    "strong": ["SOXX", "SMH", "XLK"],
    "weak": ["XLE", "XLU"],
    "risk_on_score": 0.42,
    "growth_vs_value": "growth_leading",
    "cyclical_vs_defensive": "mixed"
  },
  "biggest_moves": [
    {
      "symbol": "SOXX",
      "return_1d": 0.028,
      "trigger_type": "relative_strength",
      "evidence_type": [
        "price_confirmed",
        "relative_strength_confirmed"
      ],
      "possible_driver": "semiconductor leadership",
      "confidence": "medium",
      "uncertainty": "No confirmed fundamental event is linked to the move.",
      "watch_next": "Whether leadership broadens into XLK and QQQ."
    }
  ],
  "macro_context": {
    "rates_context": "mixed",
    "usd_context": "mixed",
    "credit_context": "risk_appetite_supportive",
    "gold_context": "gold_supported",
    "overall_regime": "mixed",
    "evidence_rows": [
      {
        "area": "Gold",
        "signal": "gold_supported",
        "evidence": "GLD 5D +1.30%",
        "interpretation": "Gold strength aligns with weaker USD or softer rate pressure."
      }
    ]
  },
  "plan_impact": [
    {
      "topic": "gold_accumulation_watch",
      "impact_level": "no_change",
      "confidence": "medium"
    }
  ]
}
```

---

## 7. LLM 使用边界

### 代码负责

```text
收益率
波动率
成交量比例
相对强弱
板块排名
异常波动筛选
状态标签
表格数据
数据缺失检测
```

### LLM 负责

```text
What Matters Today natural-language bullets
Interpretation 段落
Possible drivers 的自然语言整理
What To Watch Next
语言风格统一
摘要压缩
```

### LLM 不负责

```text
自己算涨跌
自己判断是否异常波动
无数据归因
生成买卖建议
虚构新闻或数据
虚构基本面变化
```

### Prompt 边界

```text
Do not make trading recommendations.
Do not invent news or data.
If no evidence is available, say evidence is limited.
Separate observed data from interpretation.
Mention uncertainty when confidence is low.
```

---

## 8. 当前 Report 模板

```markdown
# Daily Market Brief - {{date}}

Research support only. Not investment advice.

## 0. What Matters Today

Status: {{status}}

Drivers:
- {{driver_1}}
- {{driver_2}}
- {{driver_3}}

Reason: {{reason}}

## Data Coverage

| Category | Item | Status | Rows | Latest | Detail |
|---|---|---|---:|---|---|
{{data_coverage_rows}}

Impact:
- {{data_coverage_impact}}

## 1. Market Overview

| Asset | 1D | 5D | 20D | Volume vs 20D | Note |
|---|---:|---:|---:|---:|---|
{{market_overview_rows}}

## 2. Biggest Moves

| Asset | Move | Trigger Type | Evidence Type | Possible Driver | Confidence |
|---|---:|---|---|---|---|
{{biggest_move_rows}}

## 3. Sector Rotation

Strong: {{strong_sectors}}

Weak: {{weak_sectors}}

Risk-on score: {{risk_on_score}}

Growth vs value: {{growth_vs_value}}

Cyclical vs defensive: {{cyclical_vs_defensive}}

## 4. Macro Context

Rates: {{rates_context}}

USD: {{usd_context}}

Credit: {{credit_context}}

Gold: {{gold_context}}

Regime: {{overall_regime}}

Evidence:

| Area | Signal | Evidence | Interpretation |
|---|---|---|---|
{{macro_evidence_rows}}

## 5. Important News Clusters

{{news_clusters}}

## 6. Fundamental Events

{{fundamental_events}}

## 7. Impact On My Plan

Research support only. Not a buy/sell instruction.

{{plan_impact}}

## 8. What To Read Manually

{{manual_reading_items}}

## 9. Popular Company Price Bounds

Research support only. These are price-derived review bands, not intrinsic value.

{{company_price_bounds}}
```

---

## 9. 下一步实现优先级

当前不应优先增加更多 report section。更高价值的是把已经存在的 section 变得更可信、更可复盘。

### 9.1 signal_contract_models

负责：

```text
trigger_type
evidence_type
confidence
data_coverage state
uncertainty
watch_next
invalidation
```

建议先从 Biggest Moves / Macro Context / Plan Impact 三处接入，因为它们最容易发生“解释超过证据”的风险。

### 9.2 what_to_watch_next_analyzer

负责：

```text
根据 unusual move 生成确认 / 失效观察项
根据 sector rotation 生成 breadth / leadership 观察项
根据 macro context 生成 proxy confirmation 观察项
根据 news cluster 生成 price-confirmation 观察项
根据 fundamental event 生成 manual-read 观察项
根据 data coverage gap 生成 data-quality 观察项
```

第一版必须 deterministic，不接 LLM。

### 9.3 manual_reading_builder

负责：

```text
从 news cluster manual_read_urls 生成 reading list
从 fundamental events 生成 filing / earnings / source link review
按 confidence 和 materiality 排序
避免输出无价值的通用链接列表
```

### 9.4 market_overview_polish

负责：

```text
补回 Volume vs 20D
区分 core / sector / macro / popular company rows
避免 popular companies 淹没 core market view
```

### 9.5 optional_llm_style_layer

负责：

```text
把 deterministic output 压缩成更自然的 2-3 bullet summary
统一语气
去除重复表述
不引入新事实
不生成投资建议
```

LLM 层必须是最后一层，不能成为 analyzer。

---

## 10. Report 质量标准

判断 report 是否有用，可以用以下标准：

```text
1. 只看 What Matters Today 是否能判断今天是否值得继续读？
2. 表格是否足够少，不会堆数据？
3. 是否区分了事实和解释？
4. 是否说明了不确定性？
5. 是否避免喊单语言？
6. 是否能告诉我下一步看什么？
7. 是否和核心关注 SPY / QQQ / GLD / USD / rates 有关？
8. 是否可通过历史报告复盘？
9. quiet / unknown 是否有 Data Coverage 解释？
10. 每个解释性结论是否能追溯到 trigger 和 evidence？
```

---

## 11. 后续扩展路线

### Phase A: Signal Quality

```text
Signal contract
What To Watch Next
Manual reading list
Volume vs 20D in Market Overview
Better section ordering / grouping if report gets too long
```

### Phase B: Formal Macro Data

```text
FRED
Treasury yield
real yield
CPI / PCE
Fed expectation
DXY
```

### Phase C: Fundamentals Depth

```text
SEC filing
earnings calendar
guidance change
company event
management change
buyback / dividend
earnings transcript manual-read queue
```

### Phase D: Personal Research Mapping

```text
SPY / QQQ 长期配置观察
黄金加仓观察
美元 / 人民币换汇观察
利率与债券观察
现金利用率 / 房贷机会成本，可放周报
```

### Phase E: Weekly / Special Reports

```text
Weekly Market Structure Report
Gold Special Report
Sector Special Report
Earnings Week Preview
Macro Event Preview
```

---

## 12. 最终建议

当前最应该先做的不是新增 section，而是稳定 **Daily Market Brief 的 signal contract**。

下一步核心内容：

```text
Signal Contract
What To Watch Next
Manual Reading List
Market Overview volume / grouping polish
```

Daily report 应每天稳定回答：

```text
今天是否需要 review / monitor / ignore？
哪些信号触发了这个状态？
每个解释有没有 evidence 和 confidence？
哪些 quiet / unknown 是因为缺数据？
接下来该观察什么确认或失效信号？
```

等 signal contract 稳定后，再考虑：

```text
SEC
正式宏观数据
财报 transcript
Discord
订阅
用户交互
iOS widget
```
