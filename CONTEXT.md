# Investment Steward

The investment steward describes personal financial state across imported account
records while preserving the distinction between observed records and interpreted
economic activity.

## Language

**Statement Transaction**:
An immutable transaction record extracted from one source document and attributed to one account.
_Avoid_: Economic event, cashflow

**Economic Event**:
A financial occurrence interpreted from one or more statement transactions, such as income, spending, an internal transfer, a trade, or an FX conversion.
_Avoid_: Transaction

**Internal Transfer**:
An economic event that moves value between accounts owned by the same household without changing household wealth.
_Avoid_: Income, expense

**Transfer Candidate**:
A possible internal transfer whose statement transactions satisfy matching rules but have not been confirmed.
_Avoid_: Transfer

**External Cashflow**:
Money entering or leaving the household, excluding confirmed internal transfers.
_Avoid_: Account movement, gross cashflow

**Statement Cashflow**:
The gross credits and debits appearing in imported statement transactions before reconciliation.
_Avoid_: External cashflow

**Owned Account**:
An account included within the household whose movements may be reconciled with other owned accounts.
_Avoid_: Known account
