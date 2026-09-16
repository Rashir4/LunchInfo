"""Joe Farelli's — weekly lunch served server-rendered on /sv/lunch/.

Menu items live in div#lunch-menu as <li> elements, each holding three <p>:
label (weekday or category), dish text, price. Weekday labels are plain
Swedish day names; category items (Veckans Paleo/Vegetariska/Grill,
Fredagspizza, ...) are weekly alternatives — Fredagspizza applies to Friday
only, the rest to every weekday. Per-item prices stay out of dish text.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="joe-farellis",
    name="Joe Farelli's",
    address="Kungsportsavenyen 12, 411 36 Göteborg",
    url="https://joefarelli.com/sv/",
    menu_url="https://joefarelli.com/sv/lunch/",
    walk_minutes=12,
    cuisine="Amerikanskt",
    price="172 kr",
    lunch_hours="Mån–fre 11.30–14.30",
)


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")
    menu = soup.select_one("#lunch-menu")
    if menu is None:
        return {}

    days: dict[str, list[Dish]] = {}
    weekly: list[Dish] = []  # category items valid every weekday
    friday_only: list[Dish] = []

    for li in menu.find_all("li"):
        ps = [p.get_text(" ", strip=True) for p in li.find_all("p")]
        ps = [t for t in ps if t]
        if len(ps) < 2:
            continue
        label, dish_text = ps[0], ps[1]
        if not dish_text:
            continue
        dk = day_key(label)
        # Guard against labels like "Fredagspizza" matching the day regex:
        # a real day label is the bare day name only.
        if dk and label.strip().rstrip(":").lower() in (
            "måndag", "tisdag", "onsdag", "torsdag", "fredag"
        ):
            days.setdefault(dk, []).append(Dish(dish_text))
        elif label.strip().lower().startswith("fredagspizza"):
            friday_only.append(Dish(f"{label}: {dish_text}"))
        else:
            # Weekly alternatives: keep the label so the category is visible.
            weekly.append(Dish(f"{label}: {dish_text}"))

    if not days and not weekly and not friday_only:
        return {}

    day_keys = list(days) or list(WEEKDAYS)
    for dk in day_keys:
        for dish in weekly:
            days.setdefault(dk, []).append(Dish(dish.text, tag=dish.tag))
    for dish in friday_only:
        days.setdefault("fri", []).append(Dish(dish.text, tag=dish.tag))

    return days
