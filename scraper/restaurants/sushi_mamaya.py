"""Sushi Mamaya — Japanese eatery at Aschebergsgatan 7, Vasastan.

The /meny page is a Webflow tabs widget: both panes are in the HTML, so the
LUNCHMENY pane (``div[data-w-tab="Tab 2"]``) is readable without running any
script. Most of that pane is a standing list — sushi combos by the piece,
varmrätter, bowls — but one section, "Gästrätter (Mån - Fre)", names a
different guest dish for each weekday. That rotation is fixed rather than
weekly, so RESTAURANT.static_menu marks it; the standing à la carte items are
deliberately left out, since they belong to no particular day.

Each guest dish sits in its own ``div.div-block-11``, written as
``<strong>Måndag</strong><br><strong>Dumplings</strong><br>(beskrivning)`` —
with the day name sometimes inside the same <strong> as the dish — so parsing
works on <br>-separated text lines, not on elements.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import exact_day_key

RESTAURANT = Restaurant(
    id="sushi-mamaya",
    name="Sushi Mamaya",
    address="Aschebergsgatan 7, 411 27 Göteborg",
    url="https://www.sushimamaya.se/",
    menu_url="https://www.sushimamaya.se/meny",
    walk_minutes=12,
    cuisine="Japanskt",
    price="149 kr (gästrätt)",
    static_menu=True,
)

_LUNCH_PANE = 'div[data-w-tab="Tab 2"]'
_GUEST_HEADING = "gästrätter"
# Webflow pads the rich text with zero-width characters; strip them or a line
# holding nothing else survives .strip() and reads as an empty dish.
_ZERO_WIDTH = str.maketrans("", "", "​‌‍﻿")


def _guest_blocks(soup: BeautifulSoup) -> list:
    """The per-weekday blocks that follow the "Gästrätter" heading, or []."""
    pane = soup.select_one(_LUNCH_PANE)
    if pane is None:
        return []

    heading = next(
        (
            h
            for h in pane.select("h3.menyheading")
            if _GUEST_HEADING in h.get_text(" ", strip=True).casefold()
        ),
        None,
    )
    if heading is None:
        return []

    blocks = []
    # Walk forward from the heading's own container; a later section heading
    # (or the closing footnote) ends the guest-dish run.
    for sibling in heading.parent.find_next_siblings("div"):
        classes = sibling.get("class") or []
        if "div-block-11" in classes:
            blocks.append(sibling)
        elif "div-block-10" in classes or "div-block-12" in classes:
            break
    return blocks


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")

    days: dict[str, list[Dish]] = {}
    for block in _guest_blocks(soup):
        for br in block.find_all("br"):
            br.replace_with("\n")
        lines = [
            line
            for raw_line in block.get_text("\n").split("\n")
            if (line := raw_line.translate(_ZERO_WIDTH).strip())
        ]
        if len(lines) < 2:
            continue
        key = exact_day_key(lines[0])
        if key is None:
            continue
        days.setdefault(key, []).append(Dish(" ".join(lines[1:])))

    return days
