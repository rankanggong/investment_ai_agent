from pathlib import Path
from typing import Any

from app.models.asset import Asset, Watchlist


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

