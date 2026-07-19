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
