"""Focus Restaurang — the lunch restaurant inside ICA Focus, Gårda.

The weekly menu is published on the store's own page at ica.se and is fully
server-rendered. The layout is an intro block holding "Vecka NN", the prices
and the standing "Veckans vegetariska", followed by one ``div.fact-block`` per
day: a highlight label carrying the Swedish weekday, then a ``<ul>`` of that
day's dishes. Saturday gets a block of its own (brunch) and is dropped with
everything else that is not a weekday.

"Veckans vegetariska" is one dish that stands for the whole week, so it is
appended to every weekday instead of being lost — it is the only vegetarian
option the menu names.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import exact_day_key, week_in_text

RESTAURANT = Restaurant(
    id="focus-restaurang",
    name="Focus Restaurang",
    address="Åvägen 40, 412 51 Göteborg",
    url="https://www.ica.se/butiker/kvantum/goteborg/ica-focus-1004247/tjanster/restaurang/",
    menu_url="https://www.ica.se/butiker/kvantum/goteborg/ica-focus-1004247/tjanster/lunch/",
    walk_minutes=11,
    cuisine="Husmanskost",
    price="129 kr (salladsbar 99 kr)",
    lunch_hours="Mån–fre 11.00–14.30",
)

_DAY_LABEL = "span.ids-highlight-label__content__text"
# "Veckans vegetariska: Kantarellpasta med vitlök, ..." — one dish, all week.
_WEEKLY_VEG_RE = re.compile(r"Veckans vegetariska\s*:\s*(.+)", re.IGNORECASE)


def detect_week(raw: str) -> int | None:
    """ISO week the menu heading claims ("Vecka 38"), or None if unlabelled.

    Read off headings rather than the raw markup: the page is full of asset
    URLs and ids that a bare week pattern would match first.
    """
    soup = BeautifulSoup(raw, "lxml")
    for heading in soup.find_all(["h1", "h2", "h3"]):
        week = week_in_text(heading.get_text(" ", strip=True))
        if week:
            return week
    return None


def _weekly_veg(soup: BeautifulSoup) -> str | None:
    for p in soup.find_all("p"):
        m = _WEEKLY_VEG_RE.search(p.get_text(" ", strip=True))
        if m:
            return f"Veckans vegetariska: {m.group(1).strip()}"
    return None


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")

    days: dict[str, list[Dish]] = {}
    for block in soup.select("div.fact-block"):
        label = block.select_one(_DAY_LABEL)
        key = exact_day_key(label.get_text(" ", strip=True)) if label else None
        if key is None:
            continue  # Saturday brunch, or a block that is not a day at all
        dishes = [
            Dish(text)
            for li in block.select("li")
            if (text := li.get_text(" ", strip=True))
        ]
        if dishes:
            days.setdefault(key, []).extend(dishes)

    veg = _weekly_veg(soup)
    if veg:
        for dishes in days.values():
            dishes.append(Dish(veg))

    return days
