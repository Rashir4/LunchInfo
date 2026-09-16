"""Gaffelkonst — weekly lunch from its kvartersmenyn.se subdomain.

The restaurant's own site has no menu. We scrape the per-restaurant
subdomain (stable) rather than the numeric /rest/ URL, which has been seen
serving a different restaurant; parse() therefore verifies the page title.
kvartersmenyn injects hidden anti-scrape junk as <i> elements, and long
dish lines wrap over a <br> with a lowercase continuation line.
"""

from __future__ import annotations


from . import _kvartersmenyn
from ..models import Dish, Restaurant
from ..utils import day_key, is_day_heading

RESTAURANT = Restaurant(
    id="gaffelkonst",
    name="Gaffelkonst",
    address="Parkgatan 49, 411 38 Göteborg",
    url="http://www.gaffelkonst.se",
    menu_url="https://gaffelkonst.kvartersmenyn.se/",
    walk_minutes=17,
    cuisine="Husmanskost",
    price="149 kr",
    lunch_hours="11.00–13.30",
)

_DAY_NAMES = {"måndag", "tisdag", "onsdag", "torsdag", "fredag"}


def parse(raw: str) -> dict[str, list[Dish]]:
    lines = _kvartersmenyn.menu_lines(raw, expect_name="Gaffelkonst")
    if not lines:
        return {}

    days: dict[str, list[str]] = {}
    current: list[str] | None = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if is_day_heading(line):
            # Covers headings carrying a date ("Onsdag 17/9"); day_key maps
            # weekend headings to None, which correctly stops collection.
            key = day_key(line)
            current = days.setdefault(key, []) if key else None
            continue
        if current is None:  # anything before the first day heading
            continue
        if line[:1].islower() and current:
            # wrapped continuation of the previous dish line
            current[-1] = f"{current[-1]} {line}"
        else:
            current.append(line)

    return {
        d: [Dish(t) for t in texts] for d, texts in days.items() if texts
    }
