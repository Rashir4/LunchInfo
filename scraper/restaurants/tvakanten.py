"""Tvåkanten — weekly lunch published as a PDF linked from /menyer/.

The menu page links a per-week PDF (…/uploads/YYYY/MM/Lunch-v.-NN.pdf) behind
a "SE LUNCHMENY" button; fetch() locates the link, downloads the PDF and
returns its extracted text, which parse() consumes. Closed Mondays.
"""

from __future__ import annotations

import re

from ..models import Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="tvakanten",
    name="Tvåkanten",
    address="Kungsportsavenyn 27, 411 36 Göteborg",
    url="https://www.tvakanten.se/",
    menu_url="https://www.tvakanten.se/menyer/",
    walk_minutes=9,
    cuisine="Modern svenskt",
    price="159 kr",
    lunch_hours="Tis–fre 11.30–15.00",
)

# The weekly PDF link on /menyer/; upload path (YYYY/MM) and week number change.
_PDF_LINK_RE = re.compile(
    r'href="(https://www\.tvakanten\.se/wp-content/uploads/\d{4}/\d{2}/'
    r'Lunch-v\.-?\d+\.pdf)"'
)

# A day header on its own line: "Tisdag:", "Torsdag" (colon is inconsistent).
_DAY_LINE_RE = re.compile(
    r"^(måndag|tisdag|onsdag|torsdag|fredag)\s*:?\s*$", re.IGNORECASE
)

# All-week alternatives, e.g. "Veckans fisk |" or "Veckans vegetariska |".
_WEEKLY_RE = re.compile(
    r"^veckans\s+(fisk|vegetariska?)\s*\|?\s*(.*)$", re.IGNORECASE
)

# Trailing price like "159-", "159--" or a bare "159" at end of a dish line.
_PRICE_RE = re.compile(r"\s*\d{2,3}\s*-{0,2}\s*$")

_START_RE = re.compile(r"^veckans\s+lunch\b", re.IGNORECASE)
_STOP_RE = re.compile(r"^huvudrätter\b", re.IGNORECASE)


def fetch() -> str:
    """Locate this week's lunch PDF on the menu page and return its text."""
    from ..fetch import FetchError, fetch_html, fetch_pdf_text

    html = fetch_html(RESTAURANT.menu_url)
    m = _PDF_LINK_RE.search(html)
    if not m:
        raise FetchError("no lunch PDF link found on tvakanten.se/menyer/")
    return fetch_pdf_text(m.group(1))


def _strip_price(line: str) -> str:
    return _PRICE_RE.sub("", line).strip()


def parse(raw: str) -> dict[str, list[Dish]]:
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in raw.splitlines()]

    # Isolate the "Veckans lunch" section; stop at the à la carte mains.
    in_section = False
    section: list[str] = []
    for line in lines:
        if not line:
            continue
        if not in_section:
            if _START_RE.match(line):
                in_section = True
            continue
        if _STOP_RE.match(line):
            break
        section.append(line)

    days: dict[str, list[Dish]] = {}
    weekly: list[Dish] = []  # all-week alternatives (fish/vegetarian)
    current: str | None = None  # "tue".."fri"
    pending_weekly_tag: str | None = None
    buffer = ""

    def flush(text: str) -> None:
        text = _strip_price(text)
        if not text:
            return
        if pending_weekly_tag is not None:
            weekly.append(Dish(text, tag=pending_weekly_tag))
        elif current is not None:
            days.setdefault(current, []).append(Dish(text))

    for line in section:
        m = _DAY_LINE_RE.match(line)
        if m:
            if buffer:
                flush(buffer)
                buffer = ""
            current = day_key(m.group(1))
            pending_weekly_tag = None
            continue
        m = _WEEKLY_RE.match(line)
        if m:
            if buffer:
                flush(buffer)
                buffer = ""
            current = None
            pending_weekly_tag = "fisk" if m.group(1).lower() == "fisk" else "veg"
            rest = m.group(2).strip().lstrip("|").strip()
            if rest:
                if _PRICE_RE.search(rest):
                    flush(rest)
                    pending_weekly_tag = None
                else:
                    # No trailing price: the dish wraps onto the next PDF line,
                    # so buffer it and let the normal continuation logic finish
                    # it instead of flushing a truncated name.
                    buffer = rest
            continue
        if current is None and pending_weekly_tag is None:
            continue
        # Dish lines end in a price; a line without one is a wrapped fragment.
        buffer = f"{buffer} {line}".strip() if buffer else line
        if _PRICE_RE.search(line):
            flush(buffer)
            buffer = ""
            if pending_weekly_tag is not None:
                pending_weekly_tag = None
    if buffer:
        flush(buffer)

    # All-week dishes go into every day the restaurant serves lunch.
    day_keys = list(days) or ["tue", "wed", "thu", "fri"]
    for dk in day_keys:
        for dish in weekly:
            days.setdefault(dk, []).append(Dish(dish.text, tag=dish.tag))

    return days
