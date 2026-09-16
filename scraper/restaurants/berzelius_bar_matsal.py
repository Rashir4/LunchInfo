"""Berzelius Bar & Matsal — WordPress/Elementor, server-rendered.

Menu items are UAEL price-list widgets. There are no day headings: the day is
encoded in each item title in genitive form ("Måndagens fisk", "Tisdagens kött"),
plus "Veckans vegetariska" which is valid all week. The lunch block is duplicated
for desktop/mobile, and a static "Berzelius klassiker" section shares the same
widget markup — so items are scoped by title pattern and deduped.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant

RESTAURANT = Restaurant(
    id="berzelius-bar-matsal",
    name="Berzelius Bar & Matsal",
    address="Södra Vägen 20, 412 54 Göteborg",
    url="https://www.berzeliusbar.se/",
    menu_url="https://www.berzeliusbar.se/lunch/",
    walk_minutes=7,
    cuisine="Husmanskost",
    price="160 kr",
    lunch_hours="Mån–fre 11.30–15.00",
)

_GENITIVE_DAYS = {
    "måndagens": "mon",
    "tisdagens": "tue",
    "onsdagens": "wed",
    "torsdagens": "thu",
    "fredagens": "fri",
}

_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri")


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")
    days: dict[str, list[Dish]] = {d: [] for d in _WEEKDAYS}
    veg_dishes: list[Dish] = []
    seen: set[tuple[str, str]] = set()

    for item in soup.select("div.uael-price-list-item"):
        title_el = item.select_one("a.uael-price-list-title")
        desc_el = item.select_one("p.uael-price-list-description")
        if title_el is None or desc_el is None:
            continue
        title = title_el.get_text(" ", strip=True)
        desc = desc_el.get_text(" ", strip=True)
        if not desc:
            continue
        if (title, desc) in seen:  # desktop/mobile duplicate
            continue
        seen.add((title, desc))

        low = title.lower()
        first_word = low.split()[0] if low.split() else ""
        if first_word in _GENITIVE_DAYS:
            # "Måndagens fisk" / "Måndagens kött" — day from genitive, tag from category
            tag = "fisk" if "fisk" in low else None
            days[_GENITIVE_DAYS[first_word]].append(Dish(desc, tag=tag))
        elif low.startswith("veckans vegetariska"):
            veg_dishes.append(Dish(desc, tag="veg"))
        # anything else (e.g. "Berzelius klassiker" items) is not part of the weekly lunch

    for day in _WEEKDAYS:
        days[day].extend(veg_dishes)
    return {d: dishes for d, dishes in days.items() if dishes}
