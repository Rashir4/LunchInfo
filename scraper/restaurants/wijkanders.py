"""Wijkanders — Vera Sandbergs allé 5B (run by Chalmers Konferens & Restauranger).

The menu on wijkanders.se / chalmerskonferens.se is rendered client-side; the
underlying data comes from the Plate Impact API (see _plateimpact.py).
"""

from __future__ import annotations

from . import _plateimpact
from ..models import Dish, Restaurant

# Wijkanders' "mealProvidingUnitID" in Plate Impact, published by the
# restaurant's own WordPress data (wp-json/wp/v2/restaurant/239).
UNIT_ID = "C296E4FE-641C-4599-5874-08DE731FD655"

RESTAURANT = Restaurant(
    id="wijkanders",
    name="Wijkanders",
    address="Vera Sandbergs allé 5B",
    url="https://wijkanders.se",
    menu_url=f"https://plateimpact-screen.azurewebsites.net/menu/week/wijkanders/{UNIT_ID}",
    walk_minutes=13,
    cuisine="Husmanskost",
    price="99–129 kr",
    lunch_hours="11.00–14.00",
)

# Plate Impact dish types -> our badge tags (Kött etc. stay untagged).
_TYPE_TAGS = {"vegetarisk": "veg", "vegan": "veg", "vegansk": "veg", "fisk": "fisk"}


def fetch() -> str:
    return _plateimpact.fetch_week(UNIT_ID)


def parse(raw: str) -> dict[str, list[Dish]]:
    days: dict[str, list[Dish]] = {}
    for day, station, name in _plateimpact.iter_occurrences(raw):
        days.setdefault(day, []).append(Dish(name, _TYPE_TAGS.get(station.lower())))
    return days
