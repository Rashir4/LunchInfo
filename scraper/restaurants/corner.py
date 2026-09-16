"""Corner — comfort food at Mässans Gata 16, by Korsvägen.

The weekly lunch is a PDF linked from the lunch page; the filename carries the
week ("Lunchmeny-Corner-v38.pdf") and changes every Monday, so fetch()
re-discovers the link rather than hard-coding it. The same three dishes are
served all week — Corner publishes no per-day breakdown — so every serving day
gets the same list, the way a "veckans lunch" board works.

Lunch is Monday–Thursday: Fridays the kitchen swaps the lunch for PizzaFredag,
whose pizzas are not on this PDF, so "fri" is deliberately absent rather than
filled with dishes that are not served then.

fetch() returns the PDF's text with the source URL on the first line, which is
where the week number lives — detect_week reads it there, so a Monday morning
that still serves last week's PDF gets flagged instead of silently relabelled.
"""

from __future__ import annotations

import html as htmllib
import re

from ..models import Dish, Restaurant
from ..utils import week_in_text

RESTAURANT = Restaurant(
    id="corner",
    name="Corner",
    address="Mässans Gata 16, 412 51 Göteborg",
    url="https://cornergbg.se/",
    menu_url="https://cornergbg.se/start/restaurang/lunch/",
    walk_minutes=6,
    cuisine="Modern svenskt",
    price="135 kr",
    lunch_hours="mån–tors 11.30–14.30",
)

# Days the dagens-lunch PDF actually covers; Friday is pizza-only.
_SERVING_DAYS = ("mon", "tue", "wed", "thu")

_SOURCE_PREFIX = "source: "
_PDF_LINK_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)

# Lines that organise the menu instead of naming a dish. Matched on the heading
# only, so the "I lunchen ingår …" note under DAGENS LUNCH is dropped with it.
_SECTIONS = ("LUNCHMENY", "DAGENS LUNCH", "ALLTID PÅ LUNCHEN")


def _is_heading(line: str) -> bool:
    """True for the all-caps lines that name a dish or a section."""
    return line == line.upper() and any(ch.isalpha() for ch in line)


def fetch() -> str:
    """Find this week's lunch PDF and return its text, source URL first."""
    from ..fetch import FetchError, fetch_html, fetch_pdf_text

    page = fetch_html(RESTAURANT.menu_url)
    links = [htmllib.unescape(u) for u in _PDF_LINK_RE.findall(page)]
    menus = [u for u in links if "lunchmeny" in u.rsplit("/", 1)[-1].casefold()]
    if not menus:
        raise FetchError("no lunch PDF link found on the Corner lunch page")
    url = menus[0]
    return f"{_SOURCE_PREFIX}{url}\n{fetch_pdf_text(url)}"


def detect_week(raw: str) -> int | None:
    """The week the PDF names itself for, e.g. '…-Corner-v38.pdf'."""
    first = raw.split("\n", 1)[0]
    return week_in_text(first) if first.startswith(_SOURCE_PREFIX) else None


def _entries(raw: str) -> list[tuple[str, list[str]]]:
    """Group the PDF text into (all-caps heading, description lines) pairs."""
    entries: list[tuple[str, list[str]]] = []
    for line in raw.splitlines()[1:]:  # line 0 is the source URL
        line = line.strip()
        if not line:
            continue
        if _is_heading(line):
            entries.append((line.strip("* ").strip(), []))
        elif entries:
            entries[-1][1].append(line)
    return entries


def parse(raw: str) -> dict[str, list[Dish]]:
    dishes = [
        Dish(f"{heading} – {' '.join(body)}")
        for heading, body in _entries(raw)
        if body and not heading.startswith(_SECTIONS)
    ]
    if not dishes:
        return {}
    return {day: [Dish(d.text, tag=d.tag) for d in dishes] for day in _SERVING_DAYS}
