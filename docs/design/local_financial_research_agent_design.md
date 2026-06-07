# Local Financial Research Agent 设计草案

> 目标：构建一个本地运行、低频抓取金融信息、辅助长期投资研究的 agent / pipeline。  
> 定位：Research Assistant，不是 Trading Bot。  
> 核心原则：事实计算由代码完成，解释与报告由 LLM 辅助完成，所有结论尽量保留证据链和不确定性。

---

## 1. 项目目标

本项目希望实现一个本地金融研究助理，定期抓取并整理：

- 市场价格变化
- 板块轮动
- 金融新闻
- 宏观数据
- 公司基本面事件
- 财报 / SEC filing
- 用户关注资产与长期投资计划的影响

系统输出内容包括：

- 每日市场简报
- 每周板块与资产配置观察
- 单一标的异动归因
- 黄金 / 美股 / 债券 / 汇率专题观察
- 重要新闻聚类摘要
- 基本面事件提醒
- 值得人工阅读的原始材料列表

---

## 2. 非目标

第一阶段不做：

- 自动交易
- 高频行情
- 分钟级信号
- 期权策略自动推荐
- 加杠杆建议
- 自动生成强买卖指令
- 对未来价格做确定性预测
- 依赖 LLM 独立做财务计算
- 让通用 agent 自主浏览大量网页并直接下结论

---

## 3. 核心架构

```text
Scheduler
   ↓
Collectors
   ├── Price Collector
   ├── News Collector
   ├── Macro Collector
   ├── Filing Collector
   ├── Earnings Collector
   └── Portfolio / Watchlist Collector
   ↓
Raw Data Store
   ↓
Normalizer / Deduplicator / Tagger
   ↓
Analysis Engine
   ├── Price Move Detector
   ├── Volume / Volatility Analyzer
   ├── Sector Rotation Analyzer
   ├── Macro Context Analyzer
   ├── News Cluster Analyzer
   ├── Fundamental Event Detector
   └── Portfolio Impact Analyzer
   ↓
LLM Research Layer
   ├── News Summarizer
   ├── Move Explainer
   ├── Sector Analyst
   ├── Fundamental Analyst
   └── Report Writer
   ↓
Output Layer
   ├── Markdown Report
   ├── Local HTML Dashboard
   ├── Telegram / Email / Obsidian / Notion
   └── CLI Query Interface
```

---

## 4. 推荐技术栈

### 4.1 MVP 阶段

```text
Language: Python
Scheduler: APScheduler / cron
Database: SQLite
Analytics: pandas + DuckDB
LLM Runtime: Ollama / LM Studio / llama.cpp
Vector DB: Chroma / Qdrant，可后置
Report: Markdown
UI: CLI + local HTML
Notification: Telegram bot / Email
```

### 4.2 稳定阶段

```text
Database: PostgreSQL
Cache: Redis，可选
Task Queue: Celery / RQ，可选
Dashboard: Streamlit / FastAPI + React
Vector DB: Qdrant
Observability: structured logs + local metrics
```

---

## 5. 项目目录结构

```text
finance-agent/
  README.md
  pyproject.toml
  .env.example
  config/
    watchlist.yaml
    sources.yaml
    schedule.yaml
    user_profile.yaml
    report_config.yaml

  app/
    main.py

    collectors/
      __init__.py
      price_collector.py
      news_collector.py
      macro_collector.py
      filing_collector.py
      earnings_collector.py
      fx_collector.py
      commodity_collector.py
      portfolio_collector.py

    sources/
      __init__.py
      yfinance_source.py
      alpha_vantage_source.py
      finnhub_source.py
      fred_source.py
      sec_edgar_source.py
      rss_source.py
      newsapi_source.py
      coingecko_source.py
      manual_source.py

    normalizers/
      __init__.py
      price_normalizer.py
      news_normalizer.py
      filing_normalizer.py
      macro_normalizer.py
      symbol_resolver.py
      deduplicator.py
      tagger.py

    analyzers/
      __init__.py
      price_move_analyzer.py
      sector_rotation_analyzer.py
      volatility_analyzer.py
      macro_context_analyzer.py
      news_cluster_analyzer.py
      fundamental_event_analyzer.py
      portfolio_impact_analyzer.py
      gold_watch_analyzer.py
      currency_watch_analyzer.py

    agents/
      __init__.py
      base_agent.py
      news_summarizer.py
      move_explainer.py
      sector_analyst.py
      fundamental_analyst.py
      portfolio_impact_agent.py
      report_writer.py

    prompts/
      news_summary.md
      price_move_explain.md
      sector_analysis.md
      fundamental_event.md
      portfolio_impact.md
      daily_report.md
      weekly_report.md

    storage/
      __init__.py
      db.py
      schema.sql
      repositories/
        price_repo.py
        news_repo.py
        filing_repo.py
        macro_repo.py
        report_repo.py

    models/
      __init__.py
      asset.py
      price.py
      news.py
      filing.py
      event.py
      report.py
      portfolio.py

    jobs/
      __init__.py
      daily_market_job.py
      intraday_news_job.py
      weekly_report_job.py
      filing_check_job.py
      backfill_job.py

    outputs/
      __init__.py
      markdown_writer.py
      html_writer.py
      telegram_sender.py
      email_sender.py
      obsidian_writer.py

    utils/
      __init__.py
      time_utils.py
      retry.py
      rate_limit.py
      logging.py
      hashing.py

  data/
    finance.db
    raw/
    processed/
    reports/
    exports/

  notebooks/
    exploration.ipynb

  tests/
    test_price_analyzer.py
    test_news_dedup.py
    test_sector_rotation.py
    test_report_writer.py
```

---

## 6. 数据源候选列表

> 这里先尽量列全，不代表都要使用。最终建议按“稳定性、免费额度、覆盖范围、合法合规、实现成本”筛选。

---

### 6.1 价格数据

| 数据源 | 覆盖范围 | 优点 | 缺点 | 建议用途 |
|---|---|---|---|---|
| yfinance | 美股、ETF、指数、部分期货、外汇 | 免费、上手快、适合原型 | 非官方，稳定性和限流不可完全依赖 | MVP 价格日线 |
| Alpha Vantage | 股票、ETF、外汇、商品、加密、技术指标、部分基本面 | 覆盖广，有官方 API，也有 MCP 方向 | 免费额度有限 | MVP/正式均可 |
| Finnhub | 股票价格、公司新闻、基本面、经济日历、财报日历 | 金融 API 较完整 | 免费额度有限，高级数据需付费 | 新闻 + 财报 + 基本面 |
| Polygon.io | 美股、期权、外汇、加密 | 数据质量较好 | 付费为主 | 后续增强 |
| Tiingo | 股票、ETF、新闻 | 数据质量较好 | 免费额度有限 | 替代源 |
| Twelve Data | 股票、外汇、加密、ETF | 覆盖广 | 免费限制 | 替代源 |
| Nasdaq Data Link | 宏观、金融、另类数据 | 数据集丰富 | 许多数据集付费 | 后续增强 |
| Stooq | 股票、指数、外汇 | 免费历史数据 | API 体验一般 | 备份源 |
| Yahoo Finance 页面/RSS | 股票、ETF、新闻 | 信息丰富 | 爬虫稳定性一般 | 原型验证 |

---

### 6.2 ETF / 板块代理

| 板块 / 主题 | 代理 ETF |
|---|---|
| 美国大盘 | SPY / VOO |
| 纳斯达克 / 科技成长 | QQQ |
| 小盘 | IWM |
| 科技 | XLK |
| 通信服务 | XLC |
| 金融 | XLF |
| 能源 | XLE |
| 医疗 | XLV |
| 工业 | XLI |
| 消费可选 | XLY |
| 消费必需 | XLP |
| 公用事业 | XLU |
| 房地产 | XLRE |
| 材料 | XLB |
| 半导体 | SOXX / SMH |
| 软件 | IGV |
| 云计算 | SKYY |
| 网络安全 | CIBR |
| 生物科技 | XBI / IBB |
| 黄金 | GLD / IAU |
| 金矿股 | GDX / GDXJ |
| 长债 | TLT |
| 中期美债 | IEF |
| 短债 | SHY / BIL |
| 投资级债 | LQD |
| 高收益债 | HYG |
| 美元指数代理 | UUP |
| 原油 | USO / BNO |
| 商品综合 | DBC |

---

### 6.3 新闻数据

| 数据源 | 覆盖范围 | 优点 | 缺点 | 建议用途 |
|---|---|---|---|---|
| Google News RSS | 泛新闻 | 免费、覆盖广 | 需要去重，质量参差 | 新闻发现 |
| Yahoo Finance News | 公司和市场新闻 | 与股票关联好 | 爬取稳定性一般 | 标的新闻 |
| CNBC RSS | 市场新闻 | 时效性较好 | 摘要质量不一 | 宏观/市场 |
| Reuters | 高质量新闻 | 权威 | 直接 API/全文通常受限 | 人工阅读优先 |
| Bloomberg | 高质量金融新闻 | 权威 | 多数付费 | 人工阅读优先 |
| MarketWatch | 市场新闻 | 免费内容较多 | 噪音较多 | 辅助 |
| Seeking Alpha | 公司分析 | 深度较多 | 付费/观点强 | 观点对照 |
| Benzinga | 快讯、交易新闻 | 时效性强 | 噪音较多 | 异动归因辅助 |
| NewsAPI | 多源新闻 API | 接入方便 | 免费/版权限制 | 原型 |
| GDELT | 全球新闻事件数据 | 覆盖极广 | 噪音大，需要过滤 | 后续研究 |
| Reddit / X / Stocktwits | 社交情绪 | 能捕捉散户情绪 | 噪音、误导、合规风险 | 暂不建议第一版 |

---

### 6.4 SEC / 公司公告 / 财报

| 数据源 | 覆盖范围 | 优点 | 缺点 | 建议用途 |
|---|---|---|---|---|
| SEC EDGAR | 10-K, 10-Q, 8-K, Form 4, DEF 14A, 13F 等 | 官方、权威、免费 | 解析复杂，需要限流和 User-Agent | 核心数据源 |
| Company IR pages | 公司新闻稿、财报材料 | 官方一手资料 | 每家公司结构不同 | 核心公司可接 |
| Nasdaq Earnings Calendar | 财报日历 | 好用 | 可能需要爬取 | 财报提醒 |
| Finnhub Earnings Calendar | 财报日期、EPS 等 | API 化 | 额度限制 | MVP 可用 |
| Alpha Vantage Earnings | 财报数据 | API 化 | 覆盖和额度需验证 | 备选 |
| Financial Modeling Prep | 财报、估值、比率 | API 友好 | 免费额度有限 | 基本面增强 |
| SimFin | 标准化财务报表 | 结构化 | 覆盖有限/部分付费 | 后续增强 |

---

### 6.5 宏观数据

| 数据源 | 覆盖范围 | 优点 | 缺点 | 建议用途 |
|---|---|---|---|---|
| FRED | 利率、通胀、就业、GDP、货币、金融条件等 | 官方/权威、API 方便 | 美国为主 | 核心宏观源 |
| Federal Reserve | 利率、资产负债表、政策数据 | 官方 | 数据分散 | 核心宏观源 |
| Treasury.gov | 收益率曲线、国债数据 | 官方 | 接入需整理 | 利率分析 |
| BLS | CPI、PPI、就业 | 官方 | 发布时间固定，结构需适配 | 通胀/就业 |
| BEA | GDP、PCE、收入消费 | 官方 | 频率低 | 宏观趋势 |
| ECB / BOJ / PBOC | 央行数据 | 官方 | 接口差异大 | 后续国际宏观 |
| World Bank | 全球宏观 | 覆盖广 | 低频 | 长期背景 |
| IMF | 全球宏观金融 | 权威 | 接入复杂 | 后续增强 |
| Trading Economics | 全球宏观日历和指标 | 覆盖广 | 付费为主 | 替代源 |

---

### 6.6 外汇 / 汇率

| 数据源 | 覆盖范围 | 优点 | 缺点 | 建议用途 |
|---|---|---|---|---|
| Alpha Vantage FX | 外汇 | API 统一 | 额度限制 | MVP |
| exchangerate.host / Frankfurter | 汇率 | 简单免费 | 金融市场精度一般 | 辅助 |
| Yahoo Finance | FX tickers | 易用 | 非官方 | MVP |
| Twelve Data FX | 外汇 | API 化 | 额度限制 | 替代 |
| OANDA | 外汇 | 质量较好 | API/账户要求 | 后续 |
| 中国外汇交易中心 / 银行牌价 | CNY/CNH 相关 | 对人民币更贴近 | 接入复杂 | RMB/USD 关注 |

重点关注：

```text
USD/CNY
USD/CNH
DXY
JPY/USD 或 USD/JPY
USDCNH 与黄金、美股、换汇计划的关系
```

---

### 6.7 商品 / 黄金

| 数据源 | 覆盖范围 | 优点 | 缺点 | 建议用途 |
|---|---|---|---|---|
| GLD / IAU ETF | 黄金价格代理 | 易接入 | 不是现货金 | MVP |
| GC=F | COMEX 黄金期货 | 接近交易价格 | yfinance 依赖非官方 | MVP |
| Alpha Vantage Commodities | 商品数据 | API 统一 | 额度限制 | 替代 |
| LBMA | 伦敦金银价格 | 权威 | 接入需确认 | 后续 |
| World Gold Council | 黄金需求、央行购金报告 | 研究价值高 | 更新低频 | 基本面增强 |
| FRED real yields | 实际利率 | 黄金宏观因子 | 不是黄金数据本身 | 核心因子 |
| DXY / UUP | 美元指数代理 | 黄金重要因子 | 代理变量 | 核心因子 |

黄金观察建议指标：

```text
GLD / IAU / GC=F
DXY / UUP
10Y nominal yield
10Y real yield
TIPS yield
Fed rate expectation
央行购金新闻
地缘政治事件
ETF 持仓变化
```

---

### 6.8 加密资产，可选

| 数据源 | 覆盖范围 | 优点 | 缺点 | 建议用途 |
|---|---|---|---|---|
| CoinGecko | Crypto 价格和基本数据 | 免费友好 | 限流 | BTC/ETH 观察 |
| CoinMarketCap | Crypto 数据 | 覆盖广 | API key/额度 | 备选 |
| Binance Public API | 交易所价格 | 实时性强 | 交易所单一来源 | 若需要再接 |
| Yahoo Finance BTC-USD | BTC/ETH 价格 | 简单 | 非官方 | MVP |

---

### 6.9 Portfolio / Manual Data

| 数据 | 来源 | 用途 |
|---|---|---|
| 用户 watchlist | `config/watchlist.yaml` | 明确分析范围 |
| 用户持仓 | 手动 CSV / broker export | 组合影响分析 |
| 成本价 | 手动维护 | 盈亏和风险分析 |
| 目标配置 | 手动 YAML | 长期偏离分析 |
| 换汇计划 | 手动 YAML | RMB/USD 决策辅助 |
| 房贷利率 / 现金储备 | 手动 YAML | 机会成本分析 |

---

## 7. Watchlist 配置示例

```yaml
assets:
  core:
    - symbol: SPY
      name: S&P 500 ETF
      type: etf
      role: us_equity_core

    - symbol: QQQ
      name: Nasdaq 100 ETF
      type: etf
      role: growth_equity

    - symbol: GLD
      name: Gold ETF
      type: etf
      role: gold

    - symbol: TLT
      name: 20+ Year Treasury ETF
      type: etf
      role: duration

  sectors:
    - XLK
    - XLF
    - XLE
    - XLV
    - XLY
    - XLP
    - XLU
    - XLI
    - XLC
    - XLRE
    - SOXX
    - SMH

  macro_proxy:
    - UUP
    - BIL
    - HYG
    - LQD

  optional:
    - BTC-USD
    - USD/CNH
```

---

## 8. 用户投资 profile 示例

```yaml
user_profile:
  investment_horizon: long_term
  preferred_style: index_core_plus_tactical
  base_currency: USD
  other_currency_exposure:
    - CNY
    - JPY

  core_questions:
    - Should I continue long-term SPY/QQQ allocation?
    - Is gold entering a better accumulation zone?
    - Does USD/CNY affect my transfer timing?
    - Is my cash drag becoming too high?
    - Is mortgage prepayment better than investment?

  risk_preferences:
    avoid:
      - high_frequency_trading
      - leveraged_etf
      - unsupported_options_strategy
      - auto_trade

    prefer:
      - evidence_based_analysis
      - long_term_context
      - valuation_awareness
      - macro_context
      - source_links
      - uncertainty_labeling

  reporting_focus:
    - SPY
    - QQQ
    - GLD
    - TLT
    - USD_CNY
    - sector_rotation
    - real_yield
    - inflation
    - fed_policy
```

---

## 9. 数据库设计

### 9.1 assets

```sql
CREATE TABLE assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL UNIQUE,
  name TEXT,
  asset_type TEXT,
  sector TEXT,
  industry TEXT,
  country TEXT,
  currency TEXT,
  role TEXT,
  watch_level TEXT,
  source TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 9.2 prices

```sql
CREATE TABLE prices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  date TEXT NOT NULL,
  open REAL,
  high REAL,
  low REAL,
  close REAL,
  adjusted_close REAL,
  volume REAL,
  source TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(symbol, date, source)
);
```

### 9.3 news_items

```sql
CREATE TABLE news_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  url TEXT,
  source TEXT,
  publisher TEXT,
  published_at TEXT,
  raw_text TEXT,
  summary TEXT,
  language TEXT,
  hash TEXT UNIQUE,
  sentiment REAL,
  importance_score REAL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 9.4 news_asset_map

```sql
CREATE TABLE news_asset_map (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  news_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  relevance_score REAL,
  reason TEXT,
  FOREIGN KEY(news_id) REFERENCES news_items(id)
);
```

### 9.5 macro_series

```sql
CREATE TABLE macro_series (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  series_id TEXT NOT NULL,
  name TEXT,
  source TEXT,
  frequency TEXT,
  unit TEXT,
  description TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(series_id, source)
);
```

### 9.6 macro_observations

```sql
CREATE TABLE macro_observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  series_id TEXT NOT NULL,
  date TEXT NOT NULL,
  value REAL,
  source TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(series_id, date, source)
);
```

### 9.7 filings

```sql
CREATE TABLE filings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  cik TEXT,
  form_type TEXT,
  filing_date TEXT,
  report_date TEXT,
  accession_number TEXT UNIQUE,
  url TEXT,
  title TEXT,
  raw_text TEXT,
  summary TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 9.8 events

```sql
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type TEXT,
  title TEXT,
  description TEXT,
  event_date TEXT,
  symbols TEXT,
  sectors TEXT,
  confidence REAL,
  importance_score REAL,
  source_type TEXT,
  source_ids TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 9.9 reports

```sql
CREATE TABLE reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  report_type TEXT,
  report_date TEXT,
  title TEXT,
  content_markdown TEXT,
  source_event_ids TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 10. 核心分析模块

### 10.1 Price Move Detector

输入：

```text
symbol
daily price
historical returns
volume
sector benchmark
market benchmark
```

输出：

```json
{
  "symbol": "GLD",
  "return_1d": 0.012,
  "return_5d": 0.031,
  "return_20d": 0.058,
  "volume_ratio_20d": 1.8,
  "volatility_zscore": 1.4,
  "is_unusual_move": true,
  "reason": "1D return exceeds recent volatility threshold"
}
```

建议规则：

```text
1D return > max(3%, 1.5 * 20D avg absolute return)
volume > 2 * 20D avg volume
5D return > 2 * recent weekly volatility
sector relative return > 2%
```

---

### 10.2 Sector Rotation Analyzer

输入：

```text
sector ETF prices
SPY benchmark
QQQ benchmark
TLT / UUP / GLD
```

输出：

```json
{
  "strong_sectors": ["XLK", "SOXX"],
  "weak_sectors": ["XLU", "XLP"],
  "risk_on_score": 0.7,
  "growth_vs_value": "growth_leading",
  "cyclical_vs_defensive": "cyclical_leading",
  "notes": []
}
```

分析维度：

```text
1D / 5D / 20D relative return
sector breadth
risk-on / risk-off proxy
growth vs value
cyclical vs defensive
rate-sensitive sectors
commodity-sensitive sectors
```

---

### 10.3 News Cluster Analyzer

流程：

```text
抓取新闻
↓
标题 hash 去重
↓
URL canonicalize
↓
按 symbol / sector / macro topic 打 tag
↓
embedding 聚类，可后置
↓
每组保留代表新闻
↓
LLM 总结
```

输出：

```json
{
  "cluster_id": "2026-05-13-ai-semiconductor-demand",
  "topic": "AI semiconductor demand",
  "related_assets": ["NVDA", "AMD", "TSM", "SOXX", "SMH"],
  "event_type": "sector_demand",
  "summary": "...",
  "evidence_news_ids": [1, 2, 3],
  "confidence": 0.74,
  "is_repeated_news": false
}
```

---

### 10.4 Fundamental Event Detector

关注事件：

```text
earnings_release
guidance_change
margin_change
revenue_acceleration
revenue_deceleration
buyback
dividend_change
debt_issue
lawsuit
regulatory_event
management_change
m&a
product_launch
sec_8k
sec_10q
sec_10k
insider_transaction
```

输出：

```json
{
  "symbol": "AAPL",
  "event_type": "earnings_release",
  "fundamental_change": "moderate",
  "summary": "...",
  "positive_factors": [],
  "negative_factors": [],
  "watch_next": [],
  "confidence": 0.68
}
```

---

### 10.5 Macro Context Analyzer

核心观察：

```text
利率：
- Fed Funds Rate
- 2Y Treasury
- 10Y Treasury
- 10Y Real Yield
- Yield Curve

通胀：
- CPI
- Core CPI
- PCE
- Core PCE

就业：
- Nonfarm Payrolls
- Unemployment Rate
- Initial Claims

美元：
- DXY / UUP
- USD/CNY
- USD/CNH
- USD/JPY

风险偏好：
- SPY
- QQQ
- IWM
- HYG
- LQD
- TLT
- GLD
```

输出：

```json
{
  "macro_regime": "risk_on_with_falling_yields",
  "rate_context": "10Y yield down, duration assets supported",
  "usd_context": "USD weaker, supportive for gold",
  "gold_context": "real yield and dollar both supportive",
  "equity_context": "growth leading value",
  "confidence": 0.65
}
```

---

### 10.6 Portfolio Impact Analyzer

目标：

```text
把市场事件翻译成和用户投资计划相关的语言
```

输入：

```text
watchlist
user_profile
price signals
news clusters
macro context
fundamental events
```

输出：

```json
{
  "impact_on_user_plan": [
    {
      "topic": "Gold accumulation",
      "impact": "watch_more_closely",
      "reason": "Gold rose while real yields fell and USD weakened",
      "action_type": "observe",
      "confidence": 0.62
    }
  ],
  "not_actionable_noise": [],
  "manual_reading": []
}
```

---

## 11. LLM 使用边界

### 11.1 代码负责

```text
价格计算
收益率
波动率
成交量变化
均线
相关性
板块排名
数据清洗
去重
source tracking
阈值触发
数据库写入
```

### 11.2 LLM 负责

```text
新闻摘要
事件解释
多源信息归纳
报告生成
不确定性表达
人工阅读建议
将宏观/板块/资产变化翻译成自然语言
```

### 11.3 LLM 不负责

```text
直接计算财务指标
直接给买卖指令
没有证据地归因
替代官方财报数据
替代用户的投资决策
```

---

## 12. Agent 设计

### 12.1 不推荐单一大 agent

不推荐：

```text
One Big Financial Agent
```

原因：

```text
职责不清
prompt 过长
可复盘性差
容易胡乱调用工具
难以 debug
难以控制输出
```

### 12.2 推荐模块化 agent

```text
News Summarizer
Move Explainer
Sector Analyst
Fundamental Analyst
Portfolio Impact Agent
Report Writer
```

---

## 13. Agent 输入输出规范

### 13.1 Move Explainer Prompt Contract

输入：

```json
{
  "asset": {},
  "price_signal": {},
  "sector_context": {},
  "macro_context": {},
  "news_clusters": []
}
```

输出：

```json
{
  "symbol": "GLD",
  "move_summary": "...",
  "possible_drivers": [
    {
      "driver": "...",
      "evidence": ["..."],
      "confidence": 0.0,
      "driver_type": "macro/news/technical/fundamental"
    }
  ],
  "is_fundamental_change": "yes/no/unknown",
  "what_to_watch_next": []
}
```

规则：

```text
Do not provide trading advice.
Separate facts from interpretation.
If evidence is weak, say so.
Mention uncertainty.
Output JSON only.
```

---

### 13.2 Report Writer Contract

输入：

```json
{
  "market_overview": {},
  "sector_rotation": {},
  "macro_context": {},
  "important_news": [],
  "fundamental_events": [],
  "portfolio_impact": []
}
```

输出：

```markdown
# Daily Market Brief

## 1. Market Overview
## 2. Sector Rotation
## 3. Macro Context
## 4. Important News
## 5. Fundamental Events
## 6. Watchlist Impact
## 7. What To Read Manually
```

---

## 14. 报告模板

### 14.1 Daily Report

```markdown
# Daily Market Brief - YYYY-MM-DD

## 1. Market Overview

| Asset | 1D | 5D | 20D | Note |
|---|---:|---:|---:|---|
| SPY | | | | |
| QQQ | | | | |
| TLT | | | | |
| GLD | | | | |
| UUP | | | | |

## 2. Biggest Moves

| Asset | Move | Possible Driver | Confidence |
|---|---:|---|---:|

## 3. Sector Rotation

Strong:
Weak:
Interpretation:

## 4. Macro Context

Rates:
USD:
Gold:
Risk appetite:

## 5. Important News Clusters

### Topic 1

Summary:
Related assets:
Evidence:
Uncertainty:

## 6. Fundamental Events

New filings:
Earnings:
Guidance:
Management / regulatory events:

## 7. Impact On My Plan

SPY / QQQ:
Gold:
USD/CNY:
Cash allocation:
Mortgage opportunity cost:

## 8. What To Read Manually

1. Source title
2. Source title
```

---

### 14.2 Weekly Report

```markdown
# Weekly Investment Research Brief - Week of YYYY-MM-DD

## 1. Weekly Summary
## 2. Asset Class Performance
## 3. Sector Rotation
## 4. Macro Regime
## 5. Earnings / Fundamental Changes
## 6. Gold Watch
## 7. Currency Watch
## 8. Portfolio Relevance
## 9. Signals To Monitor Next Week
## 10. Reading List
```

---

## 15. 调度设计

### 15.1 低频默认配置

```yaml
jobs:
  price_daily:
    schedule: "weekday_after_us_close"
    frequency: "1/day"

  news_check:
    schedule: "morning_and_evening"
    frequency: "2/day"

  sec_filing_check:
    schedule: "daily"
    frequency: "1/day"

  macro_check:
    schedule: "daily"
    frequency: "1/day"

  weekly_report:
    schedule: "weekend"
    frequency: "1/week"

  deep_fundamental_review:
    trigger:
      - new_10q
      - new_10k
      - new_8k
      - earnings_release
      - abnormal_price_move
```

### 15.2 建议实际频率

| 任务 | 频率 |
|---|---|
| 价格日线 | 每天美股收盘后 |
| 新闻 | 每天 2 次 |
| SEC filing | 每天 1 次 |
| 宏观数据 | 每天 1 次 |
| 财报日历 | 每周 1 次 |
| 周报 | 每周 1 次 |
| 深度分析 | 事件触发 |

---

## 16. 数据质量与安全设计

### 16.1 数据质量

每条数据保留：

```text
source
fetched_at
original_url
raw_payload
normalized_payload
hash
version
```

### 16.2 新闻去重

去重策略：

```text
title normalized hash
url canonicalization
same publisher + same title
semantic similarity，可后置
same event tags within time window
```

### 16.3 证据链

每个 LLM 结论必须尽量关联：

```text
price_signal_id
news_ids
filing_ids
macro_series_ids
source_urls
confidence
```

### 16.4 限流

所有 collector 必须支持：

```text
rate limit
retry with backoff
timeout
source-level disable
daily quota guard
```

---

## 17. 配置文件示例

### 17.1 sources.yaml

```yaml
sources:
  price:
    primary: yfinance
    fallback:
      - alpha_vantage
      - finnhub

  news:
    primary:
      - google_news_rss
      - yahoo_finance
    fallback:
      - finnhub
      - newsapi

  macro:
    primary:
      - fred
    fallback:
      - treasury
      - bls
      - bea

  filings:
    primary:
      - sec_edgar

  commodities:
    primary:
      - yfinance
      - alpha_vantage

  crypto:
    primary:
      - coingecko
```

### 17.2 schedule.yaml

```yaml
timezone: Asia/Tokyo

daily_market_report:
  enabled: true
  time: "07:30"

news_check:
  enabled: true
  times:
    - "09:00"
    - "21:00"

weekly_report:
  enabled: true
  day: "Sunday"
  time: "10:00"
```

---

## 18. MVP 开发路线

### Phase 1: 价格和板块分析

目标：

```text
能生成没有 LLM 的价格日报
```

任务：

```text
建立 watchlist.yaml
接入价格数据
建立 SQLite schema
实现 daily return / weekly return / 20D return
实现 sector ranking
输出 markdown report
```

---

### Phase 2: 新闻抓取和摘要

目标：

```text
能解释主要异动的可能新闻背景
```

任务：

```text
接入 RSS / Yahoo / Finnhub news
实现新闻去重
实现 symbol tagging
实现 LLM 新闻摘要
把新闻 cluster 放进日报
```

---

### Phase 3: 宏观和黄金观察

目标：

```text
围绕黄金、美股、债券、美元建立宏观上下文
```

任务：

```text
接入 FRED
接入 10Y yield / real yield / inflation / Fed rate
接入 DXY / UUP / USD/CNY / USD/CNH
实现 gold_watch_analyzer
输出黄金观察段落
```

---

### Phase 4: SEC filing 和基本面事件

目标：

```text
能发现并摘要重要公司 filing
```

任务：

```text
接入 SEC EDGAR
支持 10-K / 10-Q / 8-K
实现 filing diff / event extraction
实现 fundamental_event_analyzer
输出基本面事件观察
```

---

### Phase 5: 个人投资影响分析

目标：

```text
让报告从泛市场信息变成个人投资研究助手
```

任务：

```text
建立 user_profile.yaml
建立 portfolio/watchlist role
实现 portfolio_impact_agent
报告中加入 Impact On My Plan
```

---

## 19. 与 OpenClaw / 通用 Agent 的关系

推荐架构：

```text
OpenClaw / Chat UI / Telegram
        ↓
调用本地 finance-agent CLI/API
        ↓
自研金融 pipeline
        ↓
结构化结果 / Markdown 报告
        ↓
OpenClaw 负责展示、发送、归档
```

也就是：

```bash
python -m app.jobs.daily_market_job
python -m app.main daily-report
python -m app.main explain-move --symbol GLD
python -m app.main sector-report --sector semiconductors
python -m app.main gold-watch
```

OpenClaw 不负责核心金融判断，只负责：

```text
自然语言入口
任务触发
文件保存
报告发送
调用本地命令
打开原文链接
```

---

## 20. 关键设计原则

### 20.1 Data First

先有数据，再有解释。

```text
不要让 LLM 先搜索然后直接下结论
```

---

### 20.2 Evidence First

所有结论最好有证据链。

```text
结论 = 数据 + 新闻 + filing + 宏观上下文 + 不确定性
```

---

### 20.3 Human Final Decision

系统只做研究辅助。

```text
observe / monitor / read manually
```

而不是：

```text
buy / sell / all in
```

---

### 20.4 Low Frequency First

先适配长期投资。

```text
daily / weekly
```

不要一开始做：

```text
minute-level
real-time trading
```

---

### 20.5 Modular Agents

不要一个大 agent。

```text
collector -> analyzer -> LLM summarizer -> report writer
```

---

## 21. 初始实现优先级

建议第一批只做：

```text
1. watchlist.yaml
2. price_collector
3. price_move_analyzer
4. sector_rotation_analyzer
5. markdown daily report
6. news_collector
7. news_summarizer
8. macro_context_analyzer
9. gold_watch_analyzer
10. portfolio_impact_agent
```

暂缓：

```text
SEC 深度解析
社交媒体情绪
自动回测
复杂估值模型
多账户组合同步
自动交易
```

---

## 22. 第一版最小闭环

```text
每天早上：
1. 拉取昨天美股收盘数据
2. 更新 SPY / QQQ / GLD / TLT / UUP / sector ETFs
3. 计算 1D / 5D / 20D 表现
4. 识别异动资产
5. 抓取异动资产相关新闻
6. 新闻去重和聚类
7. LLM 总结可能驱动
8. 生成 markdown report
9. 发送到 Telegram 或保存到 Obsidian
```

---

## 23. 风险和注意事项

```text
免费数据源可能不稳定
新闻源可能重复或有延迟
LLM 可能过度归因
财务数据标准化难度较高
不同 API 的 symbol 命名不一致
汇率和商品数据源需要交叉验证
报告不应构成投资建议
```

---

## 24. 后续可扩展方向

```text
估值模块：
- PE / forward PE / PS / EV/EBITDA
- earnings yield vs bond yield
- sector valuation spread

组合模块：
- target allocation
- drift detection
- cash drag analysis
- FX exposure

黄金模块：
- real yield model
- dollar sensitivity
- central bank purchase news
- ETF flow

回测模块：
- signal historical tracking
- report accuracy review
- false positive analysis

RAG 模块：
- 历史报告检索
- 公司财报检索
- 用户投资假设检索

UI 模块：
- local dashboard
- timeline view
- asset page
- event graph
```

---

## 25. 推荐命令行入口

```bash
# 初始化数据库
finance-agent init-db

# 更新价格
finance-agent collect prices

# 更新新闻
finance-agent collect news

# 更新宏观
finance-agent collect macro

# 生成日报
finance-agent report daily

# 生成周报
finance-agent report weekly

# 分析单个资产异动
finance-agent explain-move GLD

# 黄金专题
finance-agent gold-watch

# 板块报告
finance-agent sector-report semiconductors

# 检查 SEC filing
finance-agent collect filings
```

---

## 26. 当前建议结论

第一版应该是：

```text
Local Financial Research Pipeline
+
LLM Report Writer
+
Personal Watchlist Impact Layer
```

而不是：

```text
Autonomous Trading Agent
```

推荐先围绕这些资产构建：

```text
SPY
QQQ
GLD
TLT
UUP
USD/CNY
USD/CNH
XLK
XLF
XLE
XLV
XLY
XLP
XLU
SOXX
SMH
```

这样可以直接服务：

```text
美股长期配置
QQQ vs SPY
黄金加仓观察
美元/人民币换汇
利率和债券变化
板块轮动
现金利用率
```
