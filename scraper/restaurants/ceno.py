"""Ceno — lunch buffet in the World of Volvo building (Webflow, server-rendered).

https://www.ceno.se/lunch ships ALL recent weeks' menus in one Webflow CMS
list. Each dish is a div.vin-item (class names are wine-menu leftovers):
  .land      day name ("Måndag".."Fredag", or "Hela veckan" for the kids dish)
  .vin-namn  dish title
  .vin-druvor sides/description with allergens in trailing parentheses
  .vecka     ISO week number as plain text
  .vin-pris  category: "Kött" / "Fisk" / "Veg" / "Barnmeny"

The parser keeps items whose .vecka equals the current ISO week (never
hard-coded) and adds "Hela veckan" items (matched by day label, since their
.vecka is stale) to every weekday.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import current_week, day_key

RESTAURANT = Restaurant(
    id="ceno",
    name="Ceno",
    address="Lyckholms Torg 1, 412 63 Göteborg",
    url="https://www.ceno.se",
    menu_url="https://www.ceno.se/lunch",
    walk_minutes=20,
    cuisine="Modern svenskt",
    price="149 kr (buffé)",
    lunch_hours="11.00–14.30",
)

# .vin-pris category -> Dish tag (Kött/Barnmeny have no badge in the UI).
_CATEGORY_TAGS = {"fisk": "fisk", "veg": "veg"}


def _field(item, cls: str) -> str:
    el = item.select_one(f".{cls}")
    return el.get_text(" ", strip=True) if el else ""


def _dish(item) -> Dish:
    name = _field(item, "vin-namn")
    sides = _field(item, "vin-druvor")
    category = _field(item, "vin-pris")
    text = f"{name} – {sides}" if sides else name
    if category.casefold() == "barnmeny":
        text = f"Barnmeny: {text}"
    return Dish(text, tag=_CATEGORY_TAGS.get(category.casefold()))


def parse(html: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(html, "lxml")
    _, week = current_week()

    per_day: dict[str, list[Dish]] = {}
    weekly: list[Dish] = []
    for item in soup.select("div.vin-item"):
        land = _field(item, "land")
        if land.casefold() == "hela veckan":
            # Applies all week; its .vecka is a stale CMS value — match by label.
            weekly.append(_dish(item))
            continue
        # The CMS ships several weeks at once (a rolling ~6-week window, e.g.
        # 33-38), so the week number selects the current one. There is no year
        # field on the items, but the window is short enough that a
        # same-numbered week from another year is never present alongside it.
        vecka = _field(item, "vecka")
        if not vecka.isdigit() or int(vecka) != week:
            continue
        key = day_key(land)
        if key is None:
            continue
        per_day.setdefault(key, []).append(_dish(item))

    return {key: dishes + weekly for key, dishes in per_day.items()}
