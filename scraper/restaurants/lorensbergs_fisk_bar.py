"""Lorensbergs Fisk & Bar — seafood lunch at Berzeliigatan 5.

Lunch runs Tuesday–Friday (the kitchen is shut Mondays), so "mon" is absent.
Each weekday gets its own preparation of "Dagens fångst" alongside the house
räksmörgås.

The page carries no week label and nothing on it claims the rotation is new
each week, so RESTAURANT.static_menu is set: the card promises a per-weekday
rotation rather than "veckans lunch", which is the honest reading of a page
that never says which week it is for.

Markup is server-rendered: one ``div.menu-category-list`` per weekday, its
``h4.name`` holding the day name plus an "Idag" badge that the page highlights
for the current day. That badge is dropped before reading the heading — left in,
it would turn "Tisdag" into "Tisdag Idag" and no day would be recognised.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import exact_day_key

RESTAURANT = Restaurant(
    id="lorensbergs-fisk-bar",
    name="Lorensbergs Fisk & Bar",
    address="Berzeliigatan 5, 412 53 Göteborg",
    url="https://lorensbergsfisk.se/",
    menu_url="https://lorensbergsfisk.se/meny/lunch/",
    walk_minutes=4,
    cuisine="Fisk & skaldjur",
    price="165 kr",
    lunch_hours="tis–fre 11.30–14.00",
    static_menu=True,
)

# "165kr" and "255 kr" both occur; normalize the space before the unit.
_PRICE_SPACING = re.compile(r"(\d)\s*(kr|:-)\b", re.IGNORECASE)


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ")).strip()


def _day_of(block) -> str | None:
    """The weekday this menu block belongs to, ignoring the 'Idag' badge."""
    heading = block.select_one(".menu-category-list-header .name")
    if heading is None:
        return None
    for badge in heading.select(".current-day"):
        badge.decompose()
    return exact_day_key(_text(heading))


def _row_dish(row) -> Dish | None:
    """One table row: name + description in the first cell, price in the second."""
    cells = row.find_all("td", recursive=False)
    if not cells:
        return None
    parts = [_text(p) for p in cells[0].find_all("p")] or [_text(cells[0])]
    parts = [p for p in parts if p]
    if not parts:
        return None

    name, description = parts[0], " ".join(parts[1:])
    price = _PRICE_SPACING.sub(r"\1 \2", _text(cells[1])) if len(cells) > 1 else ""

    text = f"{name} {price}".strip()
    if description:
        text = f"{text} – {description}"
    return Dish(text)


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")

    days: dict[str, list[Dish]] = {}
    for block in soup.select("div.menu-category-list"):
        key = _day_of(block)
        if key is None:
            continue
        dishes = [d for d in (_row_dish(r) for r in block.select("tr")) if d]
        if dishes:
            days.setdefault(key, []).extend(dishes)
    return days
