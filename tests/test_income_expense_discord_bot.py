import asyncio
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

discord = pytest.importorskip("discord")

from app.steward.income_expense import discord_bot
from app.steward.income_expense.operations import list_entries


class FakeResponse:
    def __init__(self):
        self.messages = []
        self.deferred = False

    async def send_message(self, content, *, ephemeral):
        self.messages.append((content, ephemeral))

    async def defer(self, *, ephemeral, thinking):
        self.deferred = True

    def is_done(self):
        return self.deferred or bool(self.messages)


class FakeFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, content, *, ephemeral, view=None):
        self.messages.append((content, ephemeral, view))


def _interaction(user_id=456, guild_id=123):
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        guild_id=guild_id,
        response=FakeResponse(),
        followup=FakeFollowup(),
        message=None,
    )


def _command(client, group_name, command_name):
    guild = discord.Object(id=123)
    group = next(
        command for command in client.tree.get_commands(guild=guild)
        if command.name == group_name
    )
    return next(command for command in group.commands if command.name == command_name)


def test_bot_requires_token_and_explicit_ids(monkeypatch):
    monkeypatch.delenv("FINANCE_AGENT_DISCORD_TOKEN", raising=False)
    with pytest.raises(ValueError, match="TOKEN"):
        discord_bot.BotSettings.from_environment()
    monkeypatch.setenv("FINANCE_AGENT_DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("FINANCE_AGENT_DISCORD_GUILD_ID", "123")
    monkeypatch.setenv("FINANCE_AGENT_DISCORD_USER_ID", "456")
    settings = discord_bot.BotSettings.from_environment()
    assert (settings.guild_id, settings.user_id) == (123, 456)


def test_bot_registers_english_commands_and_rejects_other_users(tmp_path):
    settings = discord_bot.BotSettings("test-token", 123, 456, tmp_path / "ledger.db")
    client = discord_bot.FinanceDiscordClient(settings)
    guild = discord.Object(id=123)
    names = {
        group.name: {command.name for command in group.commands}
        for group in client.tree.get_commands(guild=guild)
    }
    assert names == {
        "statement": {"import"},
        "ledger": {"list", "add", "adjust"},
        "budget": {"set"},
        "report": {"month"},
    }
    unauthorized = _interaction(user_id=999)
    assert asyncio.run(client.tree.interaction_check(unauthorized)) is False
    assert unauthorized.response.messages == [("Not authorized.", True)]
    assert asyncio.run(client.tree.interaction_check(_interaction())) is True


def test_ledger_add_command_writes_audited_entry(tmp_path):
    settings = discord_bot.BotSettings("test-token", 123, 456, tmp_path / "ledger.db")
    client = discord_bot.FinanceDiscordClient(settings)
    interaction = _interaction()

    asyncio.run(
        _command(client, "ledger", "add").callback(
            interaction, "2026-10-01", "35.50", "expense", "essential",
            "Groceries", "CNY",
        )
    )

    assert interaction.response.deferred
    assert interaction.followup.messages[0][0] == "Added entry manual:1."
    assert list_entries(settings.db_path, "2026-10")[0].amount == Decimal("35.50")


def test_adjust_budget_and_report_commands(tmp_path):
    settings = discord_bot.BotSettings("test-token", 123, 456, tmp_path / "ledger.db")
    client = discord_bot.FinanceDiscordClient(settings)
    asyncio.run(
        _command(client, "ledger", "add").callback(
            _interaction(), "2000-01-03", "50", "expense", "discretionary",
            "Book", "CNY",
        )
    )
    adjusted = _interaction()
    asyncio.run(
        _command(client, "ledger", "adjust").callback(
            adjusted, "manual:1", "essential", None, "40", None,
        )
    )
    assert "Updated entry manual:1" in adjusted.followup.messages[0][0]
    budget = _interaction()
    asyncio.run(
        _command(client, "budget", "set").callback(
            budget, "2000-01", "10000", "3000", "2000", "1000", "CNY",
        )
    )
    assert "Saved budget" in budget.followup.messages[0][0]
    report = _interaction()
    asyncio.run(
        _command(client, "report", "month").callback(report, "2000-01", "CNY")
    )
    assert "Essential spending: 40.00" in report.followup.messages[0][0]
    assert "Remaining monthly allowance: 4,000.00" in report.followup.messages[0][0]


def test_statement_command_previews_before_confirming(tmp_path, monkeypatch):
    settings = discord_bot.BotSettings("test-token", 123, 456, tmp_path / "ledger.db")
    client = discord_bot.FinanceDiscordClient(settings)
    interaction = _interaction()
    preview = SimpleNamespace(
        source_hash="hash", institution="cmb", row_count=2,
        first_date="2026-10-01", last_date="2026-10-02",
        income=100, essential=20, discretionary=0, investment=0,
        warnings=(),
    )
    monkeypatch.setattr(discord_bot, "preview_import", lambda path: preview)
    confirmed = []
    monkeypatch.setattr(
        discord_bot, "confirm_import",
        lambda db, path, digest, actor: confirmed.append(
            (db, path.exists(), digest, actor)
        ) or 2,
    )

    class Attachment:
        size = 10
        filename = "statement.pdf"

        async def save(self, path):
            Path(path).write_bytes(b"%PDF-test")

    asyncio.run(
        _command(client, "statement", "import").callback(
            interaction, Attachment()
        )
    )
    view = interaction.followup.messages[0][2]
    assert "Statement preview" in interaction.followup.messages[0][0]
    assert view.pdf_path.exists()
    confirm_interaction = _interaction()
    confirm_button = next(child for child in view.children if child.label == "Confirm import")
    asyncio.run(confirm_button.callback(confirm_interaction))
    assert confirmed == [(settings.db_path, True, "hash", "discord:456")]
    assert confirm_interaction.followup.messages[0][0] == "Imported 2 statement rows."
    assert not view.pdf_path.exists()
