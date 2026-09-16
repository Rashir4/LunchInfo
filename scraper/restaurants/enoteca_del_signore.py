"""Enoteca del Signore — Italian restaurant and wine bar at Vasaplatsen 4.

The weekly lunch lives in the ``#lunch`` section of the single-page Elementor
site, server-rendered, under a "VECKA NN" heading. One text-editor widget holds
the whole menu: section labels are ``<strong>``-only paragraphs ("Varje dag",
"Måndag" … "Fredag") and dishes are ``<em>`` paragraphs, which also separates
the dishes from the trailer ("Salladsbuffé … ingår", "Glutenfri Pasta +15:-")
that carries no emphasis.

"Varje dag" lists the dishes available all week; they are appended to every
weekday after that day's own two dishes, so each card shows the full choice.

A dish that wraps onto a second line is recognised by the first line lacking a
trailing price — every complete dish entry ends in one ("169:-", "199-").
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import exact_day_key, week_in_text

RESTAURANT = Restaurant(
    id="enoteca-del-signore",
    name="Enoteca del Signore",
    address="Vasaplatsen 4, 411 34 Göteborg",
    url="https://www.signore.nu/",
    menu_url="https://www.signore.nu/#lunch",
    walk_minutes=14,
    cuisine="Italienskt",
    price="149–199 kr",
    lunch_hours="11.00–15.00",
)

# Heading that opens the dishes served every weekday.
_ALL_WEEK = "varje dag"

# A finished dish entry ends with its price: "169:-", "199-", "155 kr".
_PRICE_END = re.compile(r"\d{2,4}\s*(?::-|-|kr)\.?$", re.IGNORECASE)

# Safety valve for the continuation rule: should the kitchen ever drop prices
# altogether, this stops the whole day collapsing into one giant dish.
_MAX_CONTINUATIONS = 2


def _lunch_block(soup: BeautifulSoup):
    """The element holding the weekly lunch, or None if the page changed."""
    return soup.select_one("#lunch")


def parse(raw: str) -> dict[str, list[Dish]]:
    block = _lunch_block(BeautifulSoup(raw, "lxml"))
    if block is None:
        return {}

    all_week: list[str] = []
    days: dict[str, list[str]] = {}
    current: list[str] | None = None
    continuations = 0

    for el in block.select("p, div, li"):
        # Only leaf blocks carry menu text; skip the Elementor wrappers.
        if el.find(["p", "div", "li"]):
            continue
        text = el.get_text(" ", strip=True)
        if not text:
            continue

        if el.find("em") is None:
            # Not a dish: either a section label or surrounding page chrome.
            low = text.casefold()
            key = exact_day_key(text)
            if key:
                current = days.setdefault(key, [])
            elif low == _ALL_WEEK:
                current = all_week
            continuations = 0
            continue

        if current is None:
            continue  # dish-styled text before the first section label
        if current and not _PRICE_END.search(current[-1]) and continuations < _MAX_CONTINUATIONS:
            current[-1] = f"{current[-1]} {text}"
            continuations += 1
        else:
            current.append(text)
            continuations = 0

    result = {day: [Dish(t) for t in texts] for day, texts in days.items() if texts}
    for day in WEEKDAYS:
        if day in result:
            result[day].extend(Dish(t) for t in all_week)
    return result


def detect_week(raw: str) -> int | None:
    """ISO week the lunch block claims ("VECKA 38"), or None if unlabelled.

    Scoped to the lunch section: the surrounding page markup is full of ids and
    version strings that a bare week pattern would match first.
    """
    block = _lunch_block(BeautifulSoup(raw, "lxml"))
    if block is None:
        return None
    return week_in_text(block.get_text(" ", strip=True))
