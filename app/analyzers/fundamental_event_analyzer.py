from app.models.analysis import FundamentalEvent, NewsItem


EVENT_KEYWORDS = [
    (
        "guidance_change",
        [
            "guidance",
            "outlook",
            "forecast",
            "cuts forecast",
            "raises forecast",
            "raises outlook",
            "cuts outlook",
        ],
    ),
    (
        "earnings_release",
        ["earnings", "results", "quarterly profit", "revenue"],
    ),
    ("buyback", ["buyback", "repurchase"]),
    ("dividend_change", ["dividend", "payout"]),
    (
        "management_change",
        ["ceo", "cfo", "resigns", "appoints", "appointed"],
    ),
    (
        "regulatory_event",
        ["probe", "lawsuit", "antitrust", "sec", "regulator"],
    ),
]


def analyze_fundamental_events(
    items: list[NewsItem],
    max_events: int = 10,
) -> list[FundamentalEvent]:
    events: list[FundamentalEvent] = []
    seen_urls: set[str] = set()

    for item in items:
        if item.url in seen_urls:
            continue
        event_type = _event_type(item.title)
        if event_type is None:
            continue
        seen_urls.add(item.url)
        events.append(
            FundamentalEvent(
                event_type=event_type,
                related_symbol=item.related_symbol,
                headline=item.title,
                publisher=item.publisher,
                source_url=item.url,
                confidence=_confidence(event_type, item.title),
            )
        )

    return events[:max_events]


def _event_type(title: str) -> str | None:
    normalized = title.lower()
    for event_type, keywords in EVENT_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return event_type
    return None


def _confidence(event_type: str, title: str) -> float:
    normalized = title.lower()
    _, keywords = next(
        pair for pair in EVENT_KEYWORDS if pair[0] == event_type
    )
    matches = sum(1 for keyword in keywords if keyword in normalized)
    return min(1.0, 0.55 + matches * 0.15)
