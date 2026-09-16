"""Gowri — South Indian restaurant at Utlandagatan 14, Johanneberg.

The lunch on https://gowrirestaurang.se/lunch is a FIXED weekday rotation (the
same six dishes every Monday, every Tuesday, ...) rather than a menu that
changes each week, and the page carries no week number — RESTAURANT.static_menu
marks it so the card does not imply the dishes are new this week.

The page is server-rendered Bootstrap: each dish is a ``div.menu-item`` tagged
with an English day class (``monday`` … ``friday``) used by the on-page filter
buttons, holding the dish name in <h4> and its description in the following <p>.
The first item of each day is the day heading itself — an <h4>-less block whose
<h2> carries "MÅNDAG" — and is skipped for want of an <h4>.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant

RESTAURANT = Restaurant(
    id="gowri",
    name="Gowri",
    address="Utlandagatan 14, 412 61 Göteborg",
    url="https://gowrirestaurang.se/",
    menu_url="https://gowrirestaurang.se/lunch",
    walk_minutes=15,
    cuisine="Indiskt",
    price="120 kr",
    lunch_hours="Mån–fre 11.00–14.00",
    static_menu=True,
)

_DAY_CLASSES = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
}

# The kitchen's own catch-all vegetarian slot: no dish name gives it away.
_VEG_LABEL = "vegetariska rätter"


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")

    days: dict[str, list[Dish]] = {}
    for item in soup.select("div.menu-item"):
        classes = set(item.get("class") or [])
        day = next((_DAY_CLASSES[c] for c in classes if c in _DAY_CLASSES), None)
        if day is None:
            continue
        heading = item.find("h4")
        if heading is None:
            continue  # the day-name block, which uses <h2>
        # The chilli-strength images live inside the <h4>; get_text drops them.
        name = heading.get_text(" ", strip=True)
        if not name:
            continue
        description = item.find("p")
        text = description.get_text(" ", strip=True) if description else ""
        tag = "veg" if name.casefold() == _VEG_LABEL else None
        days.setdefault(day, []).append(
            Dish(f"{name} – {text}" if text else name, tag=tag)
        )

    return days
