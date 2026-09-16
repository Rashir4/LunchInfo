"""Bombay Street — Indian lunch, scraped from its kvartersmenyn.se page.

The restaurant's own site lists all three rotation weeks at once with no
marker for the current one, so kvartersmenyn (which carries only the current
week) is the primary source. Price on kvartersmenyn is stale (89:-); the
restaurant's own site says 129 kr, which we use as the static price.
"""

from __future__ import annotations

import re


from . import _kvartersmenyn
from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import day_key, is_day_heading

RESTAURANT = Restaurant(
    id="bombay-street",
    name="Bombay Street",
    address="Södra Vägen 77, 412 54 Göteborg",
    url="https://www.bombaystreet.se",
    menu_url="https://www.kvartersmenyn.se/rest/15808",
    walk_minutes=8,
    cuisine="Indiskt",
    price="129 kr",
    lunch_hours="11.00–15.00",
)

# Section headings that end the per-day menu (à-la-carte extras follow).
_STOP_HEADINGS = ("andra alternativ",)
# Headings whose dishes apply to every weekday.
_ALL_WEEK_HEADINGS = ("dagens veg",)


def _is_dish_name(line: str) -> bool:
    """Dish names start with an ALL-CAPS word; descriptions are sentence case."""
    m = re.match(r"([A-ZÅÄÖ]{2,})\b", line)
    return bool(m)


def parse(raw: str) -> dict[str, list[Dish]]:
    lines = _kvartersmenyn.menu_lines(raw)
    if not lines:
        return {}

    days: dict[str, list[Dish]] = {}
    all_week: list[str] = []
    current: str | None = None  # weekday key, "*" for all-week section, None = skip

    for line in lines:
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if is_day_heading(line):
            # Also matches a heading carrying a date ("TISDAG 16/9"); weekend
            # headings give key None, which stops collection until the next day.
            key = day_key(line)
            current = key
            if key:
                days.setdefault(key, [])
            continue
        if any(low.startswith(h) for h in _STOP_HEADINGS):
            break
        if any(low.startswith(h) for h in _ALL_WEEK_HEADINGS):
            current = "*"
            continue
        if current is None:  # intro boilerplate before Måndag (hours, extras)
            continue
        bucket = all_week if current == "*" else days[current]
        if _is_dish_name(line) or not bucket:
            bucket.append(line)
        else:  # lowercase description line -> attach to the preceding name
            bucket[-1] = f"{bucket[-1]} – {line}"

    result = {d: [Dish(t) for t in texts] for d, texts in days.items() if texts}
    if all_week:
        veg = [Dish(t, tag="veg") for t in all_week]
        for d in WEEKDAYS:
            if d in result:
                result[d].extend(Dish(v.text, tag=v.tag) for v in veg)
    return result
