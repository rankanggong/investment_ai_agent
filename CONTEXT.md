# Investment Steward

The investment steward describes the household's supplied cash, investment, and
foreign-exchange state without reconstructing detailed account activity.

## Language

**Asset State**:
The complete set of cash positions, holding snapshots, and FX conversions supplied for stewardship review.
_Avoid_: Ledger, transaction history

**Cash Position**:
The balance of one currency in one owned account as of a stated date.
_Avoid_: Cash transaction, cashflow

**Cash Role**:
The supplied intended use of a Cash Position: `investment_cash`,
`investment_source`, `reserved`, `emergency`, or `unknown`. Legacy imports map
`investable` to `investment_cash` and `unclassified` to `unknown`.
_Avoid_: Inferring availability from an account name

**Investment Cash**:
A Cash Position explicitly designated as immediately available for investment.
_Avoid_: Total cash, available balance

**Investment Source**:
A Cash Position designated as a funding source that may be converted or moved
before it becomes Investment Cash.
_Avoid_: Investment Cash, automatic deployability

**Reserved Cash**:
A Cash Position explicitly designated for a planned non-investment purpose.
_Avoid_: Idle cash, cash drag

**Emergency Cash**:
A Cash Position explicitly designated as an emergency reserve.
_Avoid_: Investment Cash, Reserved Cash

**Holding Snapshot**:
The quantity and supplied unit cost of one asset in one account as of a stated date.
_Avoid_: Trade, position transaction

**FX Conversion**:
A supplied record of one currency amount exchanged for another, including its date and any fee.
_Avoid_: FX suggestion, currency exposure

**Holding Cost**:
The quantity of a holding multiplied by its supplied unit cost, denominated in the holding currency.
_Avoid_: Market value, purchase amount

**Invested Sleeve Allocation**:
Each holding's share of supplied invested Holding Cost after FX conversion to
the report base currency.
_Avoid_: Market-value allocation, total liquid-asset allocation

**Total Liquid Asset Allocation**:
Each invested holding and aggregate Cash share of supplied Holding Cost plus
Cash Position balances after FX conversion. It is unavailable when cash roles
or required FX conversions are missing.
_Avoid_: Market-value allocation, deployable-capital allocation

**State Snapshot Date**:
The date on which a cash position or holding snapshot describes the owned state.
_Avoid_: Transaction date, import date

## Market Research Language

**Asset Entity**:
A uniquely identified ETF, company, index, or commodity to which evidence may be linked.
_Avoid_: Search term, ticker mention

**Query Symbol**:
The symbol used to retrieve candidate news. It is collection provenance and is not evidence that an article concerns the asset entity.
_Avoid_: Related asset

**Entity Link**:
An evidence-backed association between an article and an asset entity, with a confidence value and match reason.
_Avoid_: Query result

**Entity Precision**:
The share of candidate articles that pass the configured entity-link confidence threshold.
_Avoid_: News confidence

**Asset Event**:
One deduplicated real-world occurrence supported by one or more articles. ETF, company, index, and commodity events use separate schemas.
_Avoid_: Article, headline

**News Candidate**:
A collected headline and URL associated with the Query Symbol that retrieved it,
before entity linking. It is not yet asset evidence.
_Avoid_: Asset Event, related article

**Valuation Observation**:
A sourced value for one named valuation metric, asset, and as-of date. It is an
external observation, not an internally estimated fair value.
_Avoid_: Price target, intrinsic value

**Earnings Estimate Observation**:
A sourced consensus estimate for one asset, fiscal period, metric, and as-of date.
_Avoid_: Reported earnings, realized result

**Earnings Revision**:
The like-for-like change between the two latest Earnings Estimate Observations
from the same source, asset, fiscal period, and metric.
_Avoid_: Earnings growth, earnings surprise

**Fundamental Evidence State**:
The availability and freshness state of Valuation Observations and Earnings
Revisions, including configured materiality and resulting deterministic flags.
_Avoid_: Fundamental score, investment thesis

**Decision Evidence State**:
The quality-gated, asset-level view of Valuation Observations, Earnings
Revisions, and linked Asset Events for current Holding Snapshots and the current
Decision Candidate. It records evidence and review flags but does not infer
news sentiment or create an action.
_Avoid_: Recommendation, conviction score, news-driven trade signal

**Data Quality Gate**:
A fail-closed decision that makes news-derived scores null and portfolio action unavailable when entity precision is below threshold.
_Avoid_: Warning

**Portfolio Action**:
The availability of an explicitly configured investment rule outcome. Market evidence alone is not a portfolio action.
_Avoid_: High-conviction label, automatic de-risk instruction

**Risk Cluster**:
A configured group of correlated assets whose simultaneous signals count as
one market-risk observation.
_Avoid_: Counting every asset signal as independent risk

**Market Risk**:
The risk state derived from market prices, breadth, volatility, rates, credit,
currency, and other market evidence.
_Avoid_: Portfolio risk, report-wide data quality

**Portfolio Risk**:
The investment risk state derived from sufficiently current and classified
holdings and cash evidence. It is `unknown` when portfolio decision readiness is
blocked.
_Avoid_: Market risk, portfolio data risk

**Portfolio Decision Readiness**:
Whether supplied holdings, targets, cash roles, coverage, and snapshot freshness
are sufficient to support portfolio-specific analysis.
_Avoid_: Portfolio risk

**Portfolio Freshness**:
The separate age states of supplied Holding Snapshots, Cash Positions, and the
FX market observation used by the report.
_Avoid_: One portfolio-wide latest date

**Target Allocation Policy**:
User-supplied target weights, comparison basis, and tolerance used to evaluate
allocation gaps. An empty policy does not imply equal weighting.
_Avoid_: Model-implied target, market-value target

**Daily Investment Budget**:
The user-supplied maximum amount available to the report's daily action-sizing
calculation, in a stated currency; it is not observed spending or cash balance.
_Avoid_: Remaining cash, transaction limit

**Action Sizing Policy**:
A user-supplied mapping from a Decision Candidate action to a deterministic
fraction of the Daily Investment Budget.
_Avoid_: Strategy condition, order instruction

**Rule Execution Permission**:
A user-supplied, default-deny permission that allows one named Strategy Rule to
advance from Decision Candidate to action sizing during an optional validity period.
_Avoid_: Human approval, broker authorization, automatic execution

**Portfolio Exposure Risk**:
A score derived only from supplied investment-state facts such as allocation
gaps, invested-sleeve concentration, and investment-cash coverage.
_Avoid_: Snapshot freshness, unknown cash roles

**Portfolio Factor Exposure**:
The share of supplied invested Holding Cost associated with each configured,
possibly overlapping factor tag. It is not regression beta or market-value exposure.
_Avoid_: Factor beta, inferred style exposure

**Portfolio Impact**:
A screening score that combines Portfolio Factor Exposure with mapped Market
Risk components, clusters, and single-asset alerts. Each contribution retains
its source, points, and evidence references. The dominant factor is the largest
single factor score; overlapping tags are not summed into an expected portfolio
loss. It is not an expected gain, loss, or forecast.
_Avoid_: Price target, loss estimate

**Historical State Comparison**:
A comparison between daily report-state snapshots for decision-relevant fields,
including factor exposure, portfolio impact, readiness, and candidate changes.
_Avoid_: Transaction history, performance attribution

**Portfolio Data-Quality Risk**:
A diagnostic score describing uncertainty caused by stale or unavailable
snapshots and unknown cash roles.
_Avoid_: Portfolio exposure risk

**Capability State**:
The use-specific `available`, `limited`, `degraded`, or `blocked` status for
market, macro, portfolio, investment-action, FX, or news analysis. One blocked
capability does not automatically block the overall report.
_Avoid_: A single report-wide actionability flag

**Strategy Rule**:
A user-configured, deterministic mapping from named State metrics to one
candidate action. Each condition is evaluated as passed, failed, or blocked.
_Avoid_: GPT-created strategy, free-form recommendation

**Action Readiness**:
The deterministic condition result after Strategy Rules are evaluated:
`ready`, `blocked`, or `waiting_for_condition`. Portfolio capability and funding
constraints belong to Execution Readiness, not Action Readiness.
_Avoid_: Trade approval, execution authorization

**Decision Candidate**:
The highest-priority action produced by a triggered Strategy Rule after all
required and safety conditions are evaluable. It always requires human
approval.
_Avoid_: Order, recommendation, automatic execution

**Execution Readiness**:
Whether a Decision Candidate satisfies Rule Execution Permission, action sizing,
funding, target, and factor-mapping constraints. It never authorizes an order
and always requires human approval.
_Avoid_: Execution authorization, order

**Decision Context**:
One report-date snapshot that joins Market Risk, Portfolio Impact, current and
target allocation, Daily Investment Budget, Investment Cash, Decision Candidate,
Rule Execution Permission, both readiness states, and the Decision Evidence
State, with evidence references.
Its status describes context completeness, not permission to trade.
_Avoid_: Recommendation, order ticket, model rationale

**Decision State History**:
One persisted daily Decision Context with Action Readiness, Execution Readiness,
permission, proposed amount, rule states, evidence, and transition from the prior
snapshot.
_Avoid_: Transaction history, execution log

**Market Actionability**:
Whether market-price, breadth, volatility, and macro evidence are sufficient for
market analysis, independent of portfolio and news readiness.
_Avoid_: Overall data quality

**News Actionability**:
Whether news evidence is sufficient for causal or event-driven analysis.
_Avoid_: Market actionability, portfolio actionability

**FX Spot Premium**:
The difference between an FX Conversion's all-in effective rate and a supplied
market spot benchmark. When USD/CNH is used for CNY/USD, it is an offshore
approximation rather than an exact bank spread.
_Avoid_: Bank spread, guaranteed conversion cost

**FX State**:
The current USD investment-cash balance, configured daily USD requirement,
coverage days, latest USD/CNH spot, weighted all-in CNY/USD conversion cost
basis, and spot-to-cost-basis difference.
_Avoid_: FX recommendation, forecast

**FX Coverage Days**:
USD Investment Cash divided by the configured daily USD requirement. It is
unavailable when that requirement is absent or non-positive.
_Avoid_: FX recommendation, forecast horizon

**Absolute-Move z-score (60D)**:
The latest absolute one-day return minus the mean prior absolute one-day return,
divided by the standard deviation of prior signed daily returns within the
60-session lookback.
_Avoid_: Price-level z-score, volatility z-score

**Absolute-Move Percentile (252D)**:
The rank of the latest absolute one-day return among prior absolute daily
returns in the rolling 252-session window.
_Avoid_: Price-level percentile, VIX level percentile
