# Cluster Market Risk and Require Explicit Cash Roles

The daily report counts correlated unusual moves once per configured risk cluster
and reports market risk separately from portfolio risk. Cash availability is
supplied explicitly through `cash_role` (`investment_cash`,
`investment_source`, `reserved`, `emergency`, or `unknown`) rather than inferred
from currency, account, or balance. Legacy `investable` and `unclassified`
values are normalized on import. This
reduces double-counting in market risk and prevents reserved cash from being
treated as deployable, at the cost of maintaining the cluster map and classifying
historical cash snapshots before they can contribute to investment-cash coverage.
