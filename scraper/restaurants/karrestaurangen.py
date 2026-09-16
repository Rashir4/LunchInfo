"""Kårrestaurangen — Chalmers kårhus, Johanneberg.

Weekly menu comes from the Plate Impact API (see _plateimpact.py); the public
menu page is an Angular SPA that renders the same data client-side.
"""

from __future__ import annotations

from . import _plateimpact
from ..models import Dish, Restaurant

UNIT_ID = "21f31565-5c2b-4b47-d2a1-08d558129279"

RESTAURANT = Restaurant(
    id="karrestaurangen",
    name="Kårrestaurangen",
    address="Chalmers kårhus, Chalmersplatsen 1",
    url="https://www.chalmerskonferens.se/ata/johanneberg/karrestaurangen/",
    menu_url=(
        "https://plateimpact-screen.azurewebsites.net/menu/week/"
        f"karrestaurangen/{UNIT_ID}"
    ),
    walk_minutes=14,
    cuisine="Varierat",
    price="75–103 kr",
    lunch_hours="11.00–13.30",
)

# Serving stations in the order the restaurant lists them itself.
_STATION_ORDER = {"street food": 0, "nordic": 1, "greens": 2}
_VEGAN_STATIONS = {"greens"}  # Greens is their daily vegan station


def fetch() -> str:
    return _plateimpact.fetch_week(UNIT_ID)


def parse(raw: str) -> dict[str, list[Dish]]:
    by_day: dict[str, list[tuple[int, str, str]]] = {}
    for day, station, name in _plateimpact.iter_occurrences(raw):
        rank = _STATION_ORDER.get(station.lower(), 99)
        by_day.setdefault(day, []).append((rank, station, name))

    days: dict[str, list[Dish]] = {}
    for day, rows in by_day.items():
        dishes = [
            Dish(
                f"{station}: {name}" if station else name,
                "veg" if station.lower() in _VEGAN_STATIONS else None,
            )
            for _, station, name in sorted(rows)
        ]
        if dishes:
            days[day] = dishes
    return days
