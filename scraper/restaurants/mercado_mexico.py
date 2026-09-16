"""Mercado Mexico — Mexican lunch on Södra Vägen, Mon–Fri 11.30–14.00.

The lunch is a WEEKLY menu ("LUNCH VECKA NN") of three or four dishes — one
kött, one fisk, one veg plus a torta — and the same dishes are served every
weekday of that week, so parse() returns the whole set under each of mon–fri.

The menu itself is a PDF hosted on their Wix site. Wix mints a fresh file id
for every upload, so the PDF URL changes each week; fetch() re-discovers it
from the homepage via the button that links to it, then hands parse() the
extracted PDF text. detect_week() reads the week the PDF labels itself with,
which is how a not-yet-updated menu gets flagged instead of silently shown
as this week's.
"""

from __future__ import annotations

import html as htmllib
import re

from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import week_in_text

RESTAURANT = Restaurant(
    id="mercado-mexico",
    name="Mercado Mexico",
    address="Södra Vägen 18, 412 54 Göteborg",
    url="https://www.mercadomexico.se/",
    menu_url="https://www.mercadomexico.se/",
    walk_minutes=5,
    cuisine="Mexikanskt",
    price="145–155 kr",
    lunch_hours="Mån–fre 11.30–14.00",
)

# The homepage button linking to this week's lunch PDF. Matching on the
# aria-label (rather than on "some .pdf on the page") keeps a future catering
# or à la carte PDF from being picked up instead.
_PDF_LINK_RE = re.compile(
    r'href="([^"]+\.pdf)"[^>]*aria-label="[^"]*lunchmeny', re.IGNORECASE
)

# A section heading: a whole line in capitals, no digits ("VECKANS KÖTT",
# "TORTA DE BIRRIA"). The "LUNCH VECKA 37" title carries a number and so is
# correctly not treated as one.
_HEADING_RE = re.compile(r"^[A-ZÅÄÖÉÜ][A-ZÅÄÖÉÜ&'\- ]{2,}$")

# "VECKANS KÖTT" -> the category is the word after "VECKANS"; the dish name is
# then the first line of the section. Any other heading IS the dish name.
_CATEGORY_RE = re.compile(r"^veckans\s+(.+)$", re.IGNORECASE)

# Prices are glued to the dish name ("Milanesa de Cerdo 150kr") or stand on
# their own line under the description.
_PRICE_RE = re.compile(r"\s*\d{2,4}\s*kr\b", re.IGNORECASE)

# Category label -> Dish tag. "Kött" gets no badge, and an unlisted category
# falls through to Dish's own classification.
_CATEGORY_TAGS = {"fisk": "fisk", "veg": "veg", "vegetariskt": "veg"}


def fetch() -> str:
    """Find this week's lunch PDF on the homepage and return its text."""
    from ..fetch import FetchError, fetch_html, fetch_pdf_text

    page = fetch_html(RESTAURANT.menu_url)
    m = _PDF_LINK_RE.search(page)
    if not m:
        raise FetchError("no lunch menu PDF link found on mercadomexico.se")
    return fetch_pdf_text(htmllib.unescape(m.group(1)))


def _sections(raw: str) -> list[tuple[str, list[str]]]:
    """Split the PDF text into (heading, body lines) pairs.

    Lines before the first heading are the title and the "sallad, majschips
    ... ingår" preamble, and are dropped.
    """
    sections: list[tuple[str, list[str]]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if _HEADING_RE.match(line):
            sections.append((line, []))
        elif sections:
            sections[-1][1].append(line)
    return sections


def _dish(heading: str, body: list[str]) -> Dish | None:
    lines = [stripped for stripped in (_PRICE_RE.sub("", b).strip() for b in body) if stripped]
    if not lines:
        return None

    category = _CATEGORY_RE.match(heading)
    if category:
        name, description = lines[0], lines[1:]
        tag = _CATEGORY_TAGS.get(category.group(1).strip().casefold())
    else:
        # A heading that is not "VECKANS ..." names the dish itself (the torta),
        # and everything under it is the description.
        name, description = heading, lines
        tag = None

    text = f"{name} – {' '.join(description)}" if description else name
    return Dish(text, tag=tag)


def parse(raw: str) -> dict[str, list[Dish]]:
    dishes = [d for d in (_dish(h, b) for h, b in _sections(raw)) if d is not None]
    if not dishes:
        return {}
    # One menu for the whole week: every weekday gets the same dishes, as fresh
    # Dish objects so no day shares mutable state with another.
    return {day: [Dish(d.text, tag=d.tag) for d in dishes] for day in WEEKDAYS}


def detect_week(raw: str) -> int | None:
    """The week the PDF labels itself with ('LUNCH VECKA 37')."""
    return week_in_text(raw)
