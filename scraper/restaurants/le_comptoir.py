"""Le Comptoir Fromagerie & Bistrot — French bistro lunch on Avenyn.

The menu page (https://www.le-comptoir.se/avenylunch) is a Wix site whose
content is JS-rendered (and the HTML route intermittently returns 503), so we
scrape the underlying Wix page JSON instead: the site root HTML carries a page
registry mapping the "avenylunch" route to a versioned pageJsonFileName, which
is served from pages.parastorage.com. fetch() resolves that indirection; the
fixture is the raw page JSON body.

The menu is published weekly ("Lunchmeny v37") with a rotating plat du jour
plus bistro classics; all dishes are valid the whole week. Lunch is served
Tuesday–Friday (Mondays the bistro opens at 16:00), so "mon" is omitted.
"""

from __future__ import annotations

import html as htmllib
import json
import re
import time

from ..fetch import FetchError, fetch_html
from ..models import Dish, Restaurant

RESTAURANT = Restaurant(
    id="le-comptoir",
    name="Le Comptoir Fromagerie & Bistrot",
    address="Kungsportsavenyen 21",
    url="https://www.le-comptoir.se/",
    menu_url="https://www.le-comptoir.se/avenylunch",
    walk_minutes=10,
    cuisine="Franskt",
    price="149–205 kr",
    lunch_hours="tis–fre från 11.00",
)

_ROOT_URL = "https://www.le-comptoir.se/"
_PAGE_JSON_URL = "https://pages.parastorage.com/sites/{name}.json.z?v=3"
_PAGE_RE = re.compile(
    r'"pageUriSEO"\s*:\s*"avenylunch"\s*,\s*"pageJsonFileName"\s*:\s*"([^"]+)"'
)

# Lines that are prices / price labels, e.g. "205 kr", "154 / 164 kr".
_PRICE_RE = re.compile(r"^\d{2,4}(?:\s*/\s*\d{2,4})*\s*(?:kr|:-|sek)\.?$", re.IGNORECASE)

_BLOCK_RE = re.compile(r"<br\s*/?>|</(?:p|h\d|div|li)\s*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def _fetch_html_patiently(url: str, attempts: int = 4) -> str:
    """fetch_html with retries: the Wix frontend intermittently answers 503."""
    for attempt in range(attempts):
        try:
            return fetch_html(url)
        except FetchError:
            if attempt == attempts - 1:
                raise
            time.sleep(2.0 * (attempt + 1))
    raise FetchError(f"unreachable: {url}")  # pragma: no cover


def fetch() -> str:
    """Resolve the Wix page JSON for the /avenylunch route and return its body."""
    root = _fetch_html_patiently(_ROOT_URL)
    m = _PAGE_RE.search(root)
    if not m:
        raise ValueError("could not find avenylunch pageJsonFileName in site root")
    return _fetch_html_patiently(_PAGE_JSON_URL.format(name=m.group(1)))


def _component_lines(fragment: str) -> list[str]:
    """Visible text lines of one Wix StyledText HTML fragment.

    Inline tags (spans used for per-letter fonts) are removed without adding
    whitespace so words stay intact; block-level closers become line breaks.
    """
    text = _BLOCK_RE.sub("\n", fragment)
    text = _TAG_RE.sub("", text)
    text = htmllib.unescape(text).replace("\xa0", " ").replace("​", "")
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _ordered_texts(data: dict) -> list[str]:
    """All StyledText fragments of the page, in visual (structure) order."""
    doc = data.get("data", {}).get("document_data", {})
    order: list[str] = []

    def walk(node: object) -> None:
        if not isinstance(node, dict):
            return
        query = node.get("dataQuery")
        if isinstance(query, str):
            order.append(query.lstrip("#"))
        for child in node.get("components") or []:
            walk(child)

    walk(data.get("structure", {}))
    if not order:  # fallback: document order
        order = list(doc)

    texts = []
    for qid in order:
        entry = doc.get(qid)
        if isinstance(entry, dict) and isinstance(entry.get("text"), str):
            texts.append(entry["text"])
    return texts


def _finalize(parts: list[str]) -> Dish | None:
    if not parts:
        return None
    name = parts[0]
    if name.upper() == name:  # ALL-CAPS heading -> sentence case
        name = name.capitalize()
    text = name if len(parts) == 1 else f"{name} – {', '.join(parts[1:])}"
    tag = "veg" if re.search(r"v[eé]g[eé]tari", text, re.IGNORECASE) else None
    return Dish(text, tag)


# "Lunchmeny v37" — anchored on the word, because the raw Wix page JSON is full
# of internal ids like "v19-41" that a bare week pattern would match first.
_MENU_WEEK_RE = re.compile(r"lunch\w*\s*v\.?\s*(\d{1,2})\b", re.IGNORECASE)


def detect_week(raw: str) -> int | None:
    """ISO week this page claims ("Lunchmeny v37"), or None if unlabelled.

    The restaurant is often a week late publishing, so main.py uses this to
    flag the menu as stale rather than presenting it as the current week's.
    """
    m = _MENU_WEEK_RE.search(raw)
    if not m:
        return None
    week = int(m.group(1))
    return week if 1 <= week <= 53 else None


def parse(raw: str) -> dict[str, list[Dish]]:
    data = json.loads(raw)

    dishes: list[Dish] = []
    pending: list[str] = []
    for fragment in _ordered_texts(data):
        for line in _component_lines(fragment):
            low = line.lower()
            if "lunchmeny" in low or len(line) < 3:
                continue
            if _PRICE_RE.match(line) or low == "styckpris":
                # Price ends the current name/description group.
                dish = _finalize(pending)
                if dish:
                    dishes.append(dish)
                pending = []
                continue
            pending.append(line)
    dish = _finalize(pending)
    if dish:
        dishes.append(dish)

    # De-duplicate while preserving order (defensive against repeated blocks).
    seen: set[str] = set()
    unique = [d for d in dishes if not (d.text in seen or seen.add(d.text))]

    if not unique:
        return {}
    # Whole-week menu; no lunch service on Mondays (opens 16:00).
    return {day: list(unique) for day in ("tue", "wed", "thu", "fri")}
