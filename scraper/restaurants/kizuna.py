"""Kizuna — Japanese/Asian eatery at Gibraltargatan 8, Johanneberg.

Unlike most places here, Kizuna's lunch is a FIXED weekday rotation rather than
a menu that changes each week (their lunch PDF has been unchanged since May
2025). The rotation is still worth showing — it answers "what can I get on a
Tuesday" — but RESTAURANT.static_menu marks it so the card does not imply the
dishes are new this week.

The menu is server-rendered WordPress block markup on the /meny/ page. Day
headings are <strong>MÅNDAG</strong> inline in paragraphs that straddle day
boundaries, so parsing works on text lines rather than on elements.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import exact_day_key

RESTAURANT = Restaurant(
    id="kizuna",
    name="Kizuna",
    address="Gibraltargatan 8, 411 32 Göteborg",
    url="https://kizunaeatery.se/",
    menu_url="https://kizunaeatery.se/meny/",
    walk_minutes=7,
    cuisine="Asiatiskt",
    lunch_hours="11.00–14.30",
    static_menu=True,
)

_DAY_TEXT = re.compile(r"^\s*(måndag|tisdag|onsdag|torsdag|fredag)\s*$", re.IGNORECASE)

# Dishes wrap onto a second line that opens with the parenthesised variant,
# e.g. "Dagens varmrätt" / "(Curry Kyckling donburi)".
_CONTINUATION = re.compile(r"^\(")


def _lunch_lines(soup: BeautifulSoup) -> list[str]:
    """Text lines of the lunch block, or [] if the page no longer has one."""
    groups = [
        g for g in soup.select("div.wp-block-group")
        if len(g.find_all(string=_DAY_TEXT)) >= 5
    ]
    if not groups:
        return []
    # Several nested groups match; the smallest is the lunch block itself,
    # without the surrounding à la carte sections.
    block = min(groups, key=lambda g: len(g.get_text()))
    for br in block.find_all("br"):
        br.replace_with("\n")
    return [line.strip() for line in block.get_text("\n").split("\n") if line.strip()]


def parse(raw: str) -> dict[str, list[Dish]]:
    lines = _lunch_lines(BeautifulSoup(raw, "lxml"))

    days: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in lines:
        key = exact_day_key(line)
        if key:
            current = days.setdefault(key, [])
            continue
        if current is None:
            continue  # the "Lunch" heading, before the first day
        if _CONTINUATION.match(line) and current:
            current[-1] = f"{current[-1]} {line}"
        else:
            current.append(line)

    return {
        day: [Dish(text) for text in texts]
        for day, texts in days.items()
        if texts
    }
