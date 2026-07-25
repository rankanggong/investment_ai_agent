from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from app.models.asset import Asset, Watchlist


@dataclass(frozen=True)
class ReportProfile:
    base_currency: str = "CNY"
    target_allocations: dict[str, float] = field(default_factory=dict)
    daily_investment_budget: float | None = None
    usd_daily_spend: float | None = None
    gpt_questions: list[str] = field(default_factory=list)


def load_report_profile(path: Path | None) -> ReportProfile:
    if path is None or not path.exists():
        return ReportProfile()
    data = json.loads(path.read_text(encoding="utf-8"))
    targets = {
        str(symbol).upper(): float(weight)
        for symbol, weight in data.get("target_allocations", {}).items()
    }
    if targets and abs(sum(targets.values()) - 1.0) > 0.0001:
        raise ValueError("target_allocations must sum to 1.0")
    return ReportProfile(
        base_currency=str(data.get("base_currency", "CNY")).upper(),
        target_allocations=targets,
        daily_investment_budget=_optional_float(
            data.get("daily_investment_budget")
        ),
        usd_daily_spend=_optional_float(data.get("usd_daily_spend")),
        gpt_questions=[str(question) for question in data.get("gpt_questions", [])],
    )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def load_watchlist(path: Path) -> Watchlist:
    data = _load_yaml_like(path)
    grouped_assets = data.get("assets", {})
    assets: list[Asset] = []

    for group, entries in grouped_assets.items():
        for entry in entries:
            if isinstance(entry, dict):
                symbol = str(entry["symbol"]).upper()
                assets.append(
                    Asset(
                        symbol=symbol,
                        name=entry.get("name"),
                        asset_type=entry.get("type"),
                        role=entry.get("role", group),
                        group=group,
                    )
                )
            else:
                symbol = str(entry).upper()
                assets.append(
                    Asset(
                        symbol=symbol,
                        name=symbol,
                        asset_type="etf",
                        role=_default_role_for_group(group),
                        group=group,
                    )
                )

    return Watchlist(assets=assets)


def _default_role_for_group(group: str) -> str:
    if group == "sectors":
        return "sector"
    return group


def _load_yaml_like(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_included_watchlist(path.read_text(encoding="utf-8"))

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in {path}")
    return loaded


def _parse_included_watchlist(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {"assets": {}}
    current_group: str | None = None
    current_item: dict[str, str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "assets:":
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent == 2 and stripped.endswith(":"):
            current_group = stripped[:-1]
            result["assets"][current_group] = []
            current_item = None
            continue

        if current_group is None:
            continue

        if stripped.startswith("- "):
            value = stripped[2:]
            if ":" in value:
                key, raw_value = value.split(":", 1)
                current_item = {key.strip(): raw_value.strip()}
                result["assets"][current_group].append(current_item)
            else:
                result["assets"][current_group].append(value.strip())
                current_item = None
            continue

        if current_item is not None and ":" in stripped:
            key, raw_value = stripped.split(":", 1)
            current_item[key.strip()] = raw_value.strip()

    return result
