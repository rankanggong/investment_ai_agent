from app.analyzers.asset_event_analyzer import analyze_asset_events
from app.models.analysis import AssetEvent, NewsItem


def analyze_fundamental_events(
    items: list[NewsItem],
    max_events: int = 10,
) -> list[AssetEvent]:
    """Backward-compatible entry point for asset-specific event analysis."""
    return analyze_asset_events(items, max_events=max_events)
