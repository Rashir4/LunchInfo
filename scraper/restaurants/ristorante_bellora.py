"""Ristorante Bellora (Hotel Bellora) — weekly lunch, server-rendered WordPress.

Menu body is the div.fusion-text whose first <h4> is "DAGENS RÄTT" (numeric
class suffixes like fusion-text-9 are theme-generated — never key on them).
Days are <p><b>MÅNDAG..FREDAG</b>dish</p>; after an <h4>VECKANS RÄTTER</h4>
follow all-week options whose <b> label embeds a price
("VECKANS VEGETARISKA – 155 SEK"). Note: dashes/apostrophes are typographic
Unicode (– ’).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="ristorante-bellora",
    name="Ristorante Bellora",
    address="Kungsportsavenyn 6, 411 36 Göteborg",
    url="https://www.hotelbellora.se/restaurang/",
    menu_url="https://www.hotelbellora.se/restaurang/lunch/lunchmeny/",
    walk_minutes=11,
    cuisine="Italienskt",
    price="155 kr",
    lunch_hours="11.30–14.00",
)

# "VECKANS VEGETARISKA – 155 SEK" -> ("VECKANS VEGETARISKA", "155")
_LABEL_PRICE_RE = re.compile(r"^(.*?)\s*[–—-]\s*(\d+)\s*SEK\s*$", re.IGNORECASE)


def _menu_div(soup: BeautifulSoup):
    for div in soup.select("div.fusion-text"):
        h4 = div.find("h4")
        if h4 and h4.get_text(strip=True).casefold() == "dagens rätt":
            return div
    return None


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")
    menu = _menu_div(soup)
    if menu is None:
        return {}

    days: dict[str, list[Dish]] = {}
    weekly: list[Dish] = []
    in_weekly = False

    for el in menu.find_all(["h4", "p"]):
        if el.name == "h4":
            in_weekly = "veckans" in el.get_text(strip=True).casefold()
            continue
        label_el = el.find(["b", "strong"])
        if label_el is None:
            continue
        label = label_el.get_text(" ", strip=True)
        dish = el.get_text(" ", strip=True)
        dish = dish.removeprefix(label).strip()
        if not dish:
            continue
        if in_weekly:
            m = _LABEL_PRICE_RE.match(label)
            if m:
                name, price = m.group(1).strip().capitalize(), m.group(2)
                weekly.append(Dish(f"{name} ({price} kr): {dish}"))
            else:
                weekly.append(Dish(f"{label.capitalize()}: {dish}"))
        else:
            key = day_key(label)
            if key:
                days.setdefault(key, []).append(Dish(dish))

    days = {d: dishes for d, dishes in days.items() if dishes}
    if weekly:
        for d in WEEKDAYS:
            if d in days:
                days[d].extend(Dish(w.text, tag=w.tag) for w in weekly)
    return days
