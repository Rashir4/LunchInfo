"""S.M.A.K. — vegetarian café in Samhällsbyggnadshuset, Chalmers Johanneberg.

One vegetarian take-away lunch per weekday ("Dagens"). Weekly menu comes from
the Plate Impact API (see _plateimpact.py).
"""

from __future__ import annotations

from . import _plateimpact
from ..models import Dish, Restaurant

UNIT_ID = "3ac68e11-bcee-425e-d2a8-08d558129279"

RESTAURANT = Restaurant(
    id="smak",
    name="S.M.A.K.",
    address="Samhällsbyggnadshuset, Sven Hultins gata 6",
    url="https://www.chalmerskonferens.se/ata/johanneberg/s-m-a-k/",
    menu_url=f"https://plateimpact-screen.azurewebsites.net/menu/week/smak/{UNIT_ID}",
    walk_minutes=17,
    cuisine="Vegetariskt",
    price="75–105 kr",
    lunch_hours="07.45–16.00 (fre –15.00)",
)


def fetch() -> str:
    return _plateimpact.fetch_week(UNIT_ID)


def parse(raw: str) -> dict[str, list[Dish]]:
    days: dict[str, list[Dish]] = {}
    for day, _station, name in _plateimpact.iter_occurrences(raw):
        # The whole café is vegetarian, so tag every dish explicitly.
        days.setdefault(day, []).append(Dish(name, "veg"))
    return days
