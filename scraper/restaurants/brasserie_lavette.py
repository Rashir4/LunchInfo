"""Brasserie Lavette — Next.js site; menu lives in the __NEXT_DATA__ JSON blob.

props.pageProps.post.content holds a "weekmenublock" whose menu.weeks lists
several upcoming weeks ({year, week, menu.groups[].dishes[]}); we select the
entry matching the current ISO year+week. Each dish has title == Swedish day
name and subdishes [{title, description, price}] — the day's dagens rätt plus
standing fish and vegetarian options.
"""

from __future__ import annotations

import json

from bs4 import BeautifulSoup

from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import current_week, day_key

RESTAURANT = Restaurant(
    id="brasserie-lavette",
    name="Brasserie Lavette",
    address="Södra Vägen 30, 412 54 Göteborg",
    url="https://www.brasserielavette.se/",
    menu_url="https://www.brasserielavette.se/lunch",
    walk_minutes=4,
    cuisine="Franskt",
    price="145 kr",
    lunch_hours="Vardagar från 11.00 (buffé till 14.00)",
)


def _dish_text(subdish: dict) -> str:
    title = (subdish.get("title") or "").strip()
    description = (subdish.get("description") or "").strip()
    if title and description:
        return f"{title} {description}"
    return title or description


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None:
        return {}
    data = json.loads(script.get_text())

    content = data["props"]["pageProps"]["post"]["content"]
    block = next((b for b in content if b.get("type") == "weekmenublock"), None)
    if block is None:
        return {}

    year, week = current_week()
    weeks = block.get("menu", {}).get("weeks", [])
    entry = next(
        (
            w
            for w in weeks
            if str(w.get("year")) == str(year) and str(w.get("week")) == str(week)
        ),
        None,
    )
    if entry is None:
        return {}

    days: dict[str, list[Dish]] = {}
    weekly: list[Dish] = []  # dishes filed under a non-day title, e.g. "Hela veckan"

    for group in entry.get("menu", {}).get("groups", []):
        for day_entry in group.get("dishes", []):
            title = (day_entry.get("title") or "").strip()
            dishes = [
                Dish(text)
                for sub in day_entry.get("subdishes", [])
                if (text := _dish_text(sub))
            ]
            dk = day_key(title)
            if dk:
                days.setdefault(dk, []).extend(dishes)
            else:
                weekly.extend(dishes)

    if weekly:
        for dk in list(days) or list(WEEKDAYS):
            for dish in weekly:
                days.setdefault(dk, []).append(Dish(dish.text, tag=dish.tag))

    return days
