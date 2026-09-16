"""Lahori Masala — Pakistani/Indian kitchen at Gibraltargatan 54, by Chalmers.

Their lunch is a FIXED weekday rotation, not a menu that changes each week:
/lunch-meny lists the same four dishes for every Monday, every Tuesday and so
on. The rotation still answers "what can I get on a Thursday", so it is worth
showing, but RESTAURANT.static_menu marks it so the card does not imply the
dishes are new this week.

The page is server-rendered: ``div#menu-groups`` holds one ``div.menu-group``
per category, each with an ``<h3>`` weekday heading and Bootstrap cards whose
first ``<h5>`` is the dish name (numbered "1, ...", with chilli icons) and
whose ``p.menu-description`` is the description. The trailing "Stående
Alternativ" group is a standing à la carte list — extra naan, lassi — with no
day of its own, so it is skipped.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import exact_day_key

RESTAURANT = Restaurant(
    id="lahori-masala",
    name="Lahori Masala",
    address="Gibraltargatan 54, 412 58 Göteborg",
    url="https://www.lahorimasala.se/",
    menu_url="https://www.lahorimasala.se/lunch-meny",
    walk_minutes=15,
    cuisine="Indiskt",
    price="129 kr (inkl. kaffe, sallad, dricka, naan & ris)",
    static_menu=True,
)

# Dish names are numbered within their day: "1, Chicken Tikka Masala".
_INDEX_RE = re.compile(r"^\d+\s*[,.]\s*")


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")

    days: dict[str, list[Dish]] = {}
    for group in soup.select("#menu-groups div.menu-group"):
        heading = group.find("h3")
        key = exact_day_key(heading.get_text(" ", strip=True)) if heading else None
        if key is None:
            continue  # "Stående Alternativ" — no weekday of its own

        dishes: list[Dish] = []
        for body in group.select("div.card-body"):
            title = body.find("h5")
            if title is None:
                continue
            name = _INDEX_RE.sub("", title.get_text(" ", strip=True)).strip()
            if not name:
                continue
            desc = body.select_one("p.menu-description")
            desc_text = desc.get_text(" ", strip=True) if desc else ""
            dishes.append(Dish(f"{name} – {desc_text}" if desc_text else name))

        if dishes:
            days.setdefault(key, []).extend(dishes)

    return days
