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

**Holding Snapshot**:
The quantity and supplied unit cost of one asset in one account as of a stated date.
_Avoid_: Trade, position transaction

**FX Conversion**:
A supplied record of one currency amount exchanged for another, including its date and any fee.
_Avoid_: FX suggestion, currency exposure

**Holding Cost**:
The quantity of a holding multiplied by its supplied unit cost, denominated in the holding currency.
_Avoid_: Market value, purchase amount

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

**Data Quality Gate**:
A fail-closed decision that makes news-derived scores null and portfolio action unavailable when entity precision is below threshold.
_Avoid_: Warning

**Portfolio Action**:
The availability of an explicitly configured investment rule outcome. Market evidence alone is not a portfolio action.
_Avoid_: High-conviction label, automatic de-risk instruction
