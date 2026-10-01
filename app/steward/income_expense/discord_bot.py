"""Private Discord Gateway adapter for the daily income and expense ledger."""

from __future__ import annotations

import asyncio
import calendar
import logging
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import discord
    from discord import app_commands
except ImportError as exc:
    raise RuntimeError(
        "Discord bot requires the optional dependency: pip install -e '.[discord]'"
    ) from exc

from app.steward.income_expense.operations import (
    BudgetSettings,
    add_entry,
    adjust_entry,
    confirm_import,
    get_month_report,
    list_entries,
    preview_import,
    set_budget,
)


_LOG = logging.getLogger(__name__)
_MAX_PDF_BYTES = 15 * 1024 * 1024
_TIMEZONE = ZoneInfo("Asia/Shanghai")
_CATEGORY_CHOICES = [
    app_commands.Choice(name="Income", value="income"),
    app_commands.Choice(name="Essential", value="essential"),
    app_commands.Choice(name="Discretionary", value="discretionary"),
    app_commands.Choice(name="Investment", value="investment"),
    app_commands.Choice(name="Excluded transfer", value="excluded"),
]


@dataclass(frozen=True)
class BotSettings:
    token: str
    guild_id: int
    user_id: int
    db_path: Path

    @classmethod
    def from_environment(cls) -> BotSettings:
        token = os.environ.get("FINANCE_AGENT_DISCORD_TOKEN", "").strip()
        if not token:
            raise ValueError("FINANCE_AGENT_DISCORD_TOKEN is required.")
        try:
            guild_id = int(os.environ["FINANCE_AGENT_DISCORD_GUILD_ID"])
            user_id = int(os.environ["FINANCE_AGENT_DISCORD_USER_ID"])
        except (KeyError, ValueError) as exc:
            raise ValueError(
                "FINANCE_AGENT_DISCORD_GUILD_ID and "
                "FINANCE_AGENT_DISCORD_USER_ID must be positive integers."
            ) from exc
        if guild_id <= 0 or user_id <= 0:
            raise ValueError("Discord guild and user IDs must be positive.")
        return cls(
            token=token,
            guild_id=guild_id,
            user_id=user_id,
            db_path=Path(os.environ.get(
                "FINANCE_AGENT_INCOME_EXPENSE_DB_PATH",
                "data/steward/income_expense.db",
            )).expanduser().resolve(),
        )


def _amount(value: str) -> Decimal:
    try:
        amount = Decimal(value.strip().replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError("Amount must be a decimal number.") from exc
    if not amount.is_finite():
        raise ValueError("Amount must be finite.")
    return amount


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD.") from exc


def _month_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise ValueError("Month must use YYYY-MM.") from exc
    if len(value) != 7:
        raise ValueError("Month must use YYYY-MM.")
    return parsed


def _format_preview(preview) -> str:
    lines = [
        f"Statement preview · {preview.institution.upper()}",
        f"Rows: {preview.row_count} · {preview.first_date} to {preview.last_date}",
        f"Income: {preview.income:,.2f}",
        f"Essential: {preview.essential:,.2f}",
        f"Discretionary: {preview.discretionary:,.2f}",
        f"Investment outflow: {preview.investment:,.2f}",
    ]
    if preview.warnings:
        lines.append("Warnings: " + "; ".join(preview.warnings)[:300])
    lines.append("Confirm to save these rows.")
    return "\n".join(lines)


def _format_report(summary, allowance) -> str:
    currency = summary.currency
    return "\n".join((
        f"Monthly report · {summary.month} · {currency}",
        f"Income: {summary.income:,.2f}",
        f"Essential spending: {summary.essential:,.2f}",
        f"Discretionary spending: {summary.discretionary:,.2f}",
        f"Investment outflow: {summary.investment:,.2f}",
        "",
        f"Expected income: {allowance.expected_income:,.2f}",
        f"Essential budget: {allowance.essential_budget:,.2f}",
        f"Investment target: {allowance.investment_target:,.2f}",
        f"Safety buffer: {allowance.safety_buffer:,.2f}",
        f"Remaining monthly allowance: {allowance.remaining_monthly_allowance:,.2f}",
        f"Daily allowance: {allowance.remaining_daily_allowance:,.2f}",
        f"Days remaining: {allowance.remaining_days}",
    ))


async def _respond_error(interaction: discord.Interaction, exc: Exception) -> None:
    if isinstance(exc, (ValueError, OSError, sqlite3.Error)):
        message = str(exc)
    else:
        _LOG.exception("Discord command failed", exc_info=exc)
        message = "The operation failed. Check the bot logs."
    message = f"Error: {discord.utils.escape_mentions(message[:1700])}"
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


class ImportConfirmView(discord.ui.View):
    def __init__(
        self,
        settings: BotSettings,
        temporary: tempfile.TemporaryDirectory,
        pdf_path: Path,
        source_hash: str,
    ) -> None:
        super().__init__(timeout=600)
        self.settings = settings
        self.temporary = temporary
        self.pdf_path = pdf_path
        self.source_hash = source_hash
        self._used = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if (
            interaction.user.id == self.settings.user_id
            and interaction.guild_id == self.settings.guild_id
        ):
            return True
        await interaction.response.send_message("Not authorized.", ephemeral=True)
        return False

    def _finish(self) -> None:
        self._used = True
        self.stop()
        self.temporary.cleanup()
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Confirm import", style=discord.ButtonStyle.success)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self._used:
            await interaction.response.send_message("This preview has closed.", ephemeral=True)
            return
        self._used = True
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            count = await asyncio.to_thread(
                confirm_import,
                self.settings.db_path,
                self.pdf_path,
                self.source_hash,
                actor=f"discord:{interaction.user.id}",
            )
            await interaction.followup.send(
                f"Imported {count} statement rows.", ephemeral=True
            )
        except Exception as exc:
            await _respond_error(interaction, exc)
        finally:
            self._finish()
            if interaction.message:
                try:
                    await interaction.message.edit(view=self)
                except discord.HTTPException:
                    _LOG.warning("Could not disable the import preview buttons")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self._finish()
        await interaction.response.edit_message(content="Import cancelled.", view=self)

    async def on_timeout(self) -> None:
        self._finish()


class PrivateCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        settings = self.client.settings
        if (
            interaction.user.id == settings.user_id
            and interaction.guild_id == settings.guild_id
        ):
            return True
        await interaction.response.send_message("Not authorized.", ephemeral=True)
        return False


class FinanceDiscordClient(discord.Client):
    def __init__(self, settings: BotSettings) -> None:
        super().__init__(intents=discord.Intents.default())
        self.settings = settings
        self.tree = PrivateCommandTree(self)
        self._register_commands()

    async def setup_hook(self) -> None:
        guild = discord.Object(id=self.settings.guild_id)
        await self.tree.sync(guild=guild)

    def _register_commands(self) -> None:
        guild = discord.Object(id=self.settings.guild_id)
        statement = app_commands.Group(name="statement", description="Bank statement imports")
        ledger = app_commands.Group(name="ledger", description="Daily income and expense entries")
        budget = app_commands.Group(name="budget", description="Monthly budget settings")
        report = app_commands.Group(name="report", description="Monthly income and expenses")

        @statement.command(name="import", description="Preview and confirm a bank PDF")
        async def import_statement(
            interaction: discord.Interaction, pdf: discord.Attachment
        ) -> None:
            if pdf.size > _MAX_PDF_BYTES or not pdf.filename.lower().endswith(".pdf"):
                await interaction.response.send_message(
                    "Attach a PDF no larger than 15 MiB.", ephemeral=True
                )
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            temporary = tempfile.TemporaryDirectory(prefix="finance-discord-")
            path = Path(temporary.name) / "statement.pdf"
            try:
                await pdf.save(path)
                with path.open("rb") as handle:
                    signature = handle.read(5)
                if path.stat().st_size > _MAX_PDF_BYTES or signature != b"%PDF-":
                    raise ValueError("The attachment is not a supported PDF.")
                preview = await asyncio.to_thread(preview_import, path)
                view = ImportConfirmView(
                    self.settings, temporary, path, preview.source_hash
                )
                await interaction.followup.send(
                    _format_preview(preview), view=view, ephemeral=True
                )
            except Exception as exc:
                temporary.cleanup()
                await _respond_error(interaction, exc)

        @ledger.command(name="list", description="List recent entries for a month")
        async def list_ledger(
            interaction: discord.Interaction, month: str, currency: str = "CNY"
        ) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                rows = await asyncio.to_thread(
                    list_entries, self.settings.db_path, month,
                    currency=currency, limit=20,
                )
                lines = [f"Entries · {month} · {currency.upper()}"]
                lines.extend(
                    f"{row.reference} · {row.transaction_date} · "
                    f"{row.entry_type}/{row.category} · {row.amount:,.2f} · "
                    f"{discord.utils.escape_mentions(row.summary[:65])}"
                    for row in rows
                )
                if not rows:
                    lines.append("No entries found.")
                await interaction.followup.send(
                    "\n".join(lines)[:1900], ephemeral=True
                )
            except Exception as exc:
                await _respond_error(interaction, exc)

        @ledger.command(name="add", description="Add an income or expense entry")
        @app_commands.choices(
            kind=[
                app_commands.Choice(name="Income", value="income"),
                app_commands.Choice(name="Expense", value="expense"),
            ],
            category=_CATEGORY_CHOICES,
        )
        async def add_ledger_entry(
            interaction: discord.Interaction, date_iso: str, amount: str,
            kind: str, category: str, summary: str, currency: str = "CNY",
        ) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                reference = await asyncio.to_thread(
                    add_entry, self.settings.db_path,
                    transaction_date=_date(date_iso), currency=currency,
                    entry_type=kind, category=category, amount=_amount(amount),
                    summary=summary, actor=f"discord:{interaction.user.id}",
                )
                await interaction.followup.send(
                    f"Added entry {reference}.", ephemeral=True
                )
            except Exception as exc:
                await _respond_error(interaction, exc)

        @ledger.command(name="adjust", description="Adjust an existing entry")
        @app_commands.choices(category=_CATEGORY_CHOICES)
        async def adjust_ledger_entry(
            interaction: discord.Interaction, reference: str,
            category: str | None = None, date_iso: str | None = None,
            amount: str | None = None, summary: str | None = None,
        ) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                await asyncio.to_thread(
                    adjust_entry, self.settings.db_path, reference,
                    actor=f"discord:{interaction.user.id}", category=category,
                    transaction_date=_date(date_iso) if date_iso else None,
                    amount=_amount(amount) if amount else None,
                    summary=summary,
                )
                await interaction.followup.send(
                    f"Updated entry {reference}.", ephemeral=True
                )
            except Exception as exc:
                await _respond_error(interaction, exc)

        @budget.command(name="set", description="Set this month's budget amounts")
        async def set_month_budget(
            interaction: discord.Interaction, month: str, expected_income: str,
            essential_budget: str, investment_target: str,
            safety_buffer: str, currency: str = "CNY",
        ) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                settings = BudgetSettings(
                    month=month, currency=currency,
                    expected_income=_amount(expected_income),
                    essential_budget=_amount(essential_budget),
                    investment_target=_amount(investment_target),
                    safety_buffer=_amount(safety_buffer),
                )
                await asyncio.to_thread(
                    set_budget, self.settings.db_path, settings,
                    actor=f"discord:{interaction.user.id}",
                )
                await interaction.followup.send(
                    f"Saved budget for {month} {currency.upper()}.", ephemeral=True
                )
            except Exception as exc:
                await _respond_error(interaction, exc)

        @report.command(name="month", description="Show monthly totals and allowance")
        async def monthly_report(
            interaction: discord.Interaction, month: str, currency: str = "CNY"
        ) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                first = _month_date(month)
                today = datetime.now(_TIMEZONE).date()
                if first > today.replace(day=1):
                    raise ValueError("Future months are not available.")
                as_of = (
                    today if first.year == today.year and first.month == today.month
                    else date(first.year, first.month,
                              calendar.monthrange(first.year, first.month)[1])
                )
                summary, allowance = await asyncio.to_thread(
                    get_month_report, self.settings.db_path, month,
                    currency=currency, as_of=as_of,
                )
                await interaction.followup.send(
                    _format_report(summary, allowance), ephemeral=True
                )
            except Exception as exc:
                await _respond_error(interaction, exc)

        for group in (statement, ledger, budget, report):
            self.tree.add_command(group, guild=guild)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = BotSettings.from_environment()
    FinanceDiscordClient(settings).run(settings.token, log_handler=None)


if __name__ == "__main__":
    main()
