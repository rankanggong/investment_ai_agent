from dataclasses import dataclass


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str | None = None
    asset_type: str | None = None
    role: str | None = None
    group: str | None = None


@dataclass(frozen=True)
class Watchlist:
    assets: list[Asset]

    def asset_by_symbol(self, symbol: str) -> Asset:
        normalized = symbol.upper()
        for asset in self.assets:
            if asset.symbol.upper() == normalized:
                return asset
        raise KeyError(f"Unknown watchlist symbol: {symbol}")

    def symbols_for_group(self, group: str) -> list[str]:
        return [asset.symbol for asset in self.assets if asset.group == group]

