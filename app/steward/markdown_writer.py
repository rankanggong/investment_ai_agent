from datetime import date
from decimal import Decimal

from app.steward.analyzer import CashState
from app.steward.models import StewardState, StoredHolding


def render_steward_state_report(
    report_date: date,
    state: StewardState,
) -> str:
    lines = [
        f"# Portfolio Steward Report - {report_date.isoformat()}",
        "",
        "Research support only. Not investment, trading, tax, or FX execution advice.",
        "",
        "## 0. State Summary",
        "",
        f"- Cash positions: {len(state.cash_positions)}",
        f"- Holdings: {len(state.holdings)}",
        f"- FX conversions: {len(state.fx_conversions)}",
        "",
        "## 1. Cash Positions",
        "",
    ]
    lines.extend(_render_state_cash(state))
    lines.extend(["", "## 2. Holdings", ""])
    lines.extend(_render_state_holdings(state))
    lines.extend(["", "## 3. FX Conversions", ""])
    lines.extend(_render_state_fx(state))
    lines.extend(["", "## 4. Holding Cost By Currency", ""])
    lines.extend(_render_holding_costs(state))
    lines.extend(
        [
            "",
            "## 5. Data Notes",
            "",
            "- This report describes supplied state snapshots; it does not reconstruct transaction history.",
            "- FX conversions are recorded facts and are not automatically allocated to individual holdings.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_state_cash(state: StewardState) -> list[str]:
    if not state.cash_positions:
        return ["No cash positions supplied."]
    lines = [
        "| Institution | Account | Currency | Balance | Cash Role | As Of |",
        "|---|---|---|---:|---|---|",
    ]
    for item in state.cash_positions:
        lines.append(
            f"| {_cell(item.institution)} | {_cell(item.account_label)} | "
            f"{item.currency} | {_format_decimal(item.balance)} | "
            f"{item.cash_role} | "
            f"{item.as_of_date.isoformat()} |"
        )
    return lines


def _render_state_holdings(state: StewardState) -> list[str]:
    if not state.holdings:
        return ["No holdings supplied."]
    lines = [
        "| Institution | Account | Symbol | Name | Currency | Quantity | Unit Cost | Total Cost | As Of | Acquired On |",
        "|---|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for item in state.holdings:
        acquired_on = item.acquired_on.isoformat() if item.acquired_on else "—"
        lines.append(
            f"| {_cell(item.institution)} | {_cell(item.account_label)} | "
            f"{_cell(item.symbol)} | {_cell(item.name)} | {item.currency} | "
            f"{_format_compact(item.quantity)} | {_format_compact(item.unit_cost)} | "
            f"{_format_decimal(item.total_cost)} | {item.as_of_date.isoformat()} | "
            f"{acquired_on} |"
        )
    return lines


def _render_state_fx(state: StewardState) -> list[str]:
    if not state.fx_conversions:
        return ["No FX conversions supplied."]
    lines = [
        "| Date | Account | Sold | Bought | Effective Rate | Fee |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for item in state.fx_conversions:
        fee = f"{item.fee_currency or '—'} {_format_decimal(item.fee_amount)}"
        lines.append(
            f"| {item.fx_date.isoformat()} | {_cell(item.institution)} / "
            f"{_cell(item.account_label)} | {item.sold_currency} "
            f"{_format_decimal(item.sold_amount)} | {item.bought_currency} "
            f"{_format_decimal(item.bought_amount)} | "
            f"{_format_rate(item.effective_rate)} {item.sold_currency}/"
            f"{item.bought_currency} | {fee} |"
        )
    return lines


def _render_holding_costs(state: StewardState) -> list[str]:
    costs: dict[str, Decimal] = {}
    for item in state.holdings:
        costs[item.currency] = costs.get(item.currency, Decimal("0")) + item.total_cost
    if not costs:
        return ["No holding costs supplied."]
    lines = ["| Currency | Total Cost |", "|---|---:|"]
    for currency, cost in sorted(costs.items()):
        lines.append(f"| {currency} | {_format_decimal(cost)} |")
    return lines


def _cell(value: str) -> str:
    return value.replace("|", "\\|")


def _format_compact(value: Decimal) -> str:
    return format(value, "f")


def _format_rate(value: Decimal) -> str:
    return f"{value:.4f}"


def render_steward_report(
    report_date: date,
    cash_state: CashState,
    document_count: int,
    holdings: list[StoredHolding],
) -> str:
    lines = [
        f"# Portfolio Steward Report - {report_date.isoformat()}",
        "",
        "Research support only. Not investment, trading, tax, or FX execution advice.",
        "",
        "## 0. State Summary",
        "",
        f"Imported source documents: {document_count}",
        "",
        f"Normalized cash transactions: {len(cash_state.recent_transactions)} recent shown",
        "",
        f"Manual holdings: {len(holdings)}",
        "",
        "## 1. Data Coverage",
        "",
        "- Local-folder import only.",
        "- Cash transaction statements are supported for Alipay CSV, CMB PDF text, and ICBC PDF text.",
        "- Brokerage positions can be supplied through the manual holdings CSV import.",
        "- Brokerage statement parsers and email monitoring are not enabled in stage 1.",
        "",
        "## 2. Account Balances",
        "",
    ]
    lines.extend(_render_account_balances(cash_state))
    lines.extend(
        [
            "",
            "## 2A. Manual Holdings",
            "",
        ]
    )
    lines.extend(_render_holdings(holdings))
    lines.extend(
        [
            "",
            "## 3. External Cashflow By Currency",
            "",
        ]
    )
    lines.extend(_render_cashflows(cash_state))
    lines.extend(
        [
            "",
            "## 4. Statement Cashflow By Currency",
            "",
        ]
    )
    lines.extend(_render_cashflow_rows(cash_state.statement_cashflows))
    lines.extend(
        [
            "",
            "## 5. Confirmed Internal Transfers",
            "",
        ]
    )
    lines.extend(_render_transfers(cash_state.confirmed_transfers))
    lines.extend(
        [
            "",
            "## 6. Transfer Candidates",
            "",
        ]
    )
    lines.extend(_render_transfers(cash_state.suggested_transfers))
    lines.extend(
        [
            "",
            "Candidates remain in external cashflow until confirmed.",
            "",
            "## 7. Recent Cash Transactions",
            "",
        ]
    )
    lines.extend(_render_recent_transactions(cash_state))
    lines.extend(
        [
            "",
            "## 8. FX Review",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in cash_state.fx_review)
    lines.extend(
        [
            "",
            "## 9. Exceptions / Manual Checks",
            "",
            "- Review parser warnings from import output before relying on totals.",
            "- Confirm account ownership and duplicate statement windows manually.",
        ]
    )
    lines.extend(
        f"- Reconciliation: {warning}"
        for warning in cash_state.reconciliation_warnings
    )
    lines.append("")
    return "\n".join(lines)


def _render_account_balances(cash_state: CashState) -> list[str]:
    if not cash_state.account_balances:
        return ["No statement balance rows available."]
    lines = [
        "| Institution | Account | Currency | Balance | As Of |",
        "|---|---|---|---:|---|",
    ]
    for item in cash_state.account_balances:
        lines.append(
            f"| {item.institution} | {item.account_label} | {item.currency} | "
            f"{_format_decimal(item.balance)} | {item.as_of.isoformat()} |"
        )
    return lines


def _render_cashflows(cash_state: CashState) -> list[str]:
    return _render_cashflow_rows(cash_state.cashflows)


def _render_holdings(holdings: list[StoredHolding]) -> list[str]:
    if not holdings:
        return ["No manual holdings imported."]
    lines = [
        "| Institution | Account | Symbol | Name | Currency | Quantity | Unit Cost | Total Cost | Acquired On | FX Transaction ID |",
        "|---|---|---|---|---|---:|---:|---:|---|---:|",
    ]
    for holding in holdings:
        fx_transaction_id = (
            str(holding.fx_transaction_id)
            if holding.fx_transaction_id is not None
            else "—"
        )
        lines.append(
            f"| {holding.institution} | {holding.account_label} | "
            f"{holding.symbol} | {holding.name} | {holding.currency} | "
            f"{_format_decimal(holding.quantity)} | "
            f"{_format_decimal(holding.unit_cost)} | "
            f"{_format_decimal(holding.quantity * holding.unit_cost)} | "
            f"{holding.acquired_on.isoformat()} | {fx_transaction_id} |"
        )
    return lines


def _render_cashflow_rows(cashflows) -> list[str]:
    if not cashflows:
        return ["No cashflow rows available."]
    lines = [
        "| Currency | Inflow | Outflow | Net |",
        "|---|---:|---:|---:|",
    ]
    for item in cashflows:
        lines.append(
            f"| {item.currency} | {_format_decimal(item.inflow)} | "
            f"{_format_decimal(item.outflow)} | {_format_decimal(item.net)} |"
        )
    return lines


def _render_transfers(transfers) -> list[str]:
    if not transfers:
        return ["No transfers in this status."]
    lines = [
        "| Out ID | In ID | From | To | Currency | Amount | Fee | Dates |",
        "|---:|---:|---|---|---|---:|---:|---|",
    ]
    for item in transfers:
        lines.append(
            f"| {item.outgoing_transaction_id} | {item.incoming_transaction_id} | "
            f"{item.outgoing_institution} / {item.outgoing_account} | "
            f"{item.incoming_institution} / {item.incoming_account} | "
            f"{item.currency} | {_format_decimal(item.amount)} | "
            f"{_format_decimal(item.fee)} | {item.outgoing_date.isoformat()} -> "
            f"{item.incoming_date.isoformat()} |"
        )
    return lines


def _render_recent_transactions(cash_state: CashState) -> list[str]:
    if not cash_state.recent_transactions:
        return ["No recent transactions available."]
    lines = [
        "| ID | Date | Institution | Account | Currency | Amount | Summary |",
        "|---:|---|---|---|---|---:|---|",
    ]
    for txn in cash_state.recent_transactions:
        lines.append(
            f"| {txn.id} | {txn.transaction_date.isoformat()} | {txn.institution} | "
            f"{txn.account_label} | {txn.currency} | {_format_decimal(txn.amount)} | "
            f"{txn.summary} |"
        )
    return lines


def _format_decimal(value: Decimal) -> str:
    return f"{value:.2f}"
