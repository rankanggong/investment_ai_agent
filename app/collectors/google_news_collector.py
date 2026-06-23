from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import urlopen
import xml.etree.ElementTree as ET

from app.models.analysis import NewsItem


Fetcher = Callable[[str], str]


@dataclass(frozen=True)
class NewsCollectionResult:
    items: list[NewsItem]
    failed_symbols: list[str]
    failure_reasons: dict[str, str] = field(default_factory=dict)


def collect_google_news(
    symbols: Iterable[str],
    fetcher: Fetcher | None = None,
) -> NewsCollectionResult:
    load = fetcher or _fetch_google_news_rss
    items: list[NewsItem] = []
    failed_symbols: list[str] = []
    failure_reasons: dict[str, str] = {}

    for raw_symbol in symbols:
        symbol = raw_symbol.upper()
        try:
            rss_text = load(symbol)
            items.extend(_parse_rss_items(rss_text, symbol))
        except Exception as error:
            failed_symbols.append(symbol)
            failure_reasons[symbol] = _describe_error(error)

    return NewsCollectionResult(
        items=items,
        failed_symbols=failed_symbols,
        failure_reasons=failure_reasons,
    )


def _fetch_google_news_rss(query: str) -> str:
    params = urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    url = f"https://news.google.com/rss/search?{params}"
    with urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8")


def _parse_rss_items(rss_text: str, symbol: str) -> list[NewsItem]:
    root = ET.fromstring(rss_text)
    return [_element_to_item(element, symbol) for element in root.findall(".//item")]


def _element_to_item(element: ET.Element, symbol: str) -> NewsItem:
    source = element.find("source")
    return NewsItem(
        title=_text(element, "title"),
        url=_canonical_url(_text(element, "link")),
        publisher=source.text.strip() if source is not None and source.text else None,
        published_at=_parse_date(_text(element, "pubDate")),
        related_symbol=symbol,
        source="google_news_rss",
    )


def _text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    return parsedate_to_datetime(value)


def _canonical_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _describe_error(error: Exception) -> str:
    detail = str(error).strip()
    error_type = type(error).__name__
    return f"{error_type}: {detail}" if detail else error_type
