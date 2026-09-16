"""Glenn Sportsbar Ullevi — weekly lunch from the Divi-built location page.

The lunch section is <div id="Lunch Ullevi"> (note the literal space in the id,
so it is found via find(id=...), not a #-selector). Days are <h3>Måndag..Fredag</h3>
inside div.et_pb_text_inner blocks spread over two columns; each dish is a <p>
after its day heading. "Veckans vegetariska" applies to the whole week;
the static "Alltid på Glenn" items (burgers/salads with inline prices) are skipped.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="glenn-sportsbar-ullevi",
    name="Glenn Sportsbar Ullevi",
    address="Skånegatan 1, 411 40 Göteborg",
    url="https://www.glennsportsbar.se/",
    menu_url="https://www.glennsportsbar.se/ullevi/",
    walk_minutes=18,
    cuisine="Husmanskost",
    price="145 kr",
    lunch_hours="11.00–13.30",
)


def parse(html: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(html, "lxml")
    section = soup.find("div", id="Lunch Ullevi")
    if section is None:
        return {}

    days: dict[str, list[Dish]] = {}
    weekly: list[Dish] = []  # "Veckans vegetariska" — valid every weekday
    current: str | None = None  # a day key, "weekly", or None (ignore)

    # Numeric et_pb_text_NN class suffixes shift between builds; iterate every
    # text block inside the lunch section instead.
    for inner in section.select("div.et_pb_text_inner"):
        for el in inner.find_all(["h2", "h3", "p"]):
            text = el.get_text(" ", strip=True)
            if not text:
                continue
            if el.name in ("h2", "h3"):
                key = day_key(text)
                if key:
                    current = key
                elif text.lower().startswith("veckans vegetariska"):
                    current = "weekly"
                else:
                    # "Lunch v NN" header, "Alltid på Glenn" statics, etc.
                    current = None
                continue
            if current is None:
                continue
            if current == "weekly":
                weekly.append(Dish(text, tag="veg"))
            else:
                days.setdefault(current, []).append(Dish(text))

    if weekly:
        for key in list(days) or list(WEEKDAYS):
            days.setdefault(key, []).extend(Dish(d.text, tag=d.tag) for d in weekly)
    return days
