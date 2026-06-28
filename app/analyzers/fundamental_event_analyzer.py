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
                review_type=_review_type(event_type),
                why_it_matters=_why_it_matters(event_type),
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


def _review_type(event_type: str) -> str:
    review_type_by_event = {
        "earnings_release": "earnings_review",
        "guidance_change": "guidance_review",
        "buyback": "capital_return_review",
        "dividend_change": "capital_return_review",
        "management_change": "governance_review",
        "regulatory_event": "regulatory_risk_review",
    }
    return review_type_by_event.get(event_type, "fundamental_review")


def _why_it_matters(event_type: str) -> str:
    why_by_event = {
        "earnings_release": "Earnings releases can reset revenue, margin, cash-flow, and valuation assumptions.",
        "guidance_change": "Guidance changes can alter forward estimates and valuation support.",
        "buyback": "Buybacks can affect capital return, share count, and management confidence signals.",
        "dividend_change": "Dividend changes can signal cash-flow confidence or balance-sheet pressure.",
        "management_change": "Management changes can alter execution risk and strategic direction.",
        "regulatory_event": "Regulatory events can create legal, financial, or operating constraints.",
    }
    return why_by_event.get(event_type, "This event may affect fundamental assumptions.")
