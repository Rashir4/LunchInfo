"""Sofina — deli/catering kitchen on Lorensbergsgatan.

The menu page (https://sofina.net/lunch-1/ = always the current week) renders
client-side, but the full dataset is embedded in the static HTML as an inline
JS array:  var items = [ ['DD-MM-YYYY', 'DISH NAME', 'Description ...', PRICE], ... ]
holding years of history plus a few future weeks, so parse() filters the rows
to the Mon-Fri dates of the current ISO week.
"""

from __future__ import annotations

import datetime as dt
import re

from ..models import Dish, Restaurant
from ..utils import current_week

RESTAURANT = Restaurant(
    id="sofina",
    name="Sofina",
    address="Lorensbergsgatan 18, 411 36 Göteborg",
    url="https://sofina.net",
    menu_url="https://sofina.net/lunch-1/",
    walk_minutes=8,
    cuisine="Husmanskost",
    price="129 kr (avhämtning)",
    lunch_hours="Mån–fre 10.00–19.00",
)

# ['14-09-2026', 'DISH NAME', 'Description ... allergen codes', 129]
# JS string fields may contain escaped apostrophes (l\'orange), so each field
# matches "any non-quote, or a backslash-escaped character".
_JS_STR = r"(?:[^'\\]|\\.)*"
_ITEM_RE = re.compile(
    rf"\[\s*'({_JS_STR})',\s*'({_JS_STR})',\s*'({_JS_STR})',\s*(\d+)\s*\]"
)

# Undo JS string escaping in a captured field.
_UNESCAPE_RE = re.compile(r"\\(.)")

# Trailing allergen shorthand at the end of descriptions: "G-L-Ä", "L-Ä", "G" ...
_ALLERGEN_RE = re.compile(r"\s+[GLÄ](?:\s*-\s*[GLÄ])*\s*$")


def parse(raw: str) -> dict[str, list[Dish]]:
    year, week = current_week()
    # ISO weekday 1..5 -> date of that weekday in the current week.
    week_dates = {
        dt.date.fromisocalendar(year, week, i).strftime("%d-%m-%Y"): key
        for i, key in enumerate(("mon", "tue", "wed", "thu", "fri"), start=1)
    }

    days: dict[str, list[Dish]] = {}
    for date_str, name, desc, _price in _ITEM_RE.findall(raw):
        date_str = _UNESCAPE_RE.sub(r"\1", date_str)
        name = _UNESCAPE_RE.sub(r"\1", name)
        desc = _UNESCAPE_RE.sub(r"\1", desc)
        day = week_dates.get(date_str)
        if day is None:
            continue  # historical or future week
        name = name.strip()
        desc = _ALLERGEN_RE.sub("", desc.strip()).strip()
        if not name:
            continue
        text = f"{name} – {desc}" if desc else name
        days.setdefault(day, []).append(Dish(text))
    return days
