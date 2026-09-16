"""Restaurang Näckrosen — Nordrest campus restaurant at Humanisten (GU).

The weekly menu is served by the Castit menu widget on hors.se
(Högskolerestauranger / Nordrest) and is fully server-rendered:
one `div.castit-weekpanel[data-week]` per published week, containing a
`section.castit-day` per weekday with title + description per dish.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import current_week, day_key

RESTAURANT = Restaurant(
    id="nackrosen",
    name="Restaurang Näckrosen",
    address="Renströmsgatan 6",
    url="https://www.hors.se/goteborg/17/6/restaurang-nackrosen/",
    menu_url="https://www.hors.se/goteborg/17/6/restaurang-nackrosen/",
    walk_minutes=4,
    cuisine="Varierat",
    price="",
    lunch_hours="11.00–13.30",
)


def _pick_week_panel(soup: BeautifulSoup):
    """The panel for the current ISO week; fall back to active/first/whole page."""
    panels = soup.select("div.castit-weekpanel")
    if not panels:
        return soup
    if len(panels) > 1:
        _, week = current_week()
        for panel in panels:
            if panel.get("data-week") == str(week):
                return panel
        for panel in panels:
            if "is-active" in (panel.get("class") or []):
                return panel
    return panels[0]


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")
    panel = _pick_week_panel(soup)

    days: dict[str, list[Dish]] = {}
    for section in panel.select("section.castit-day"):
        title_el = section.select_one(".castit-day__title")
        key = day_key(title_el.get_text(" ", strip=True)) if title_el else None
        if not key:
            continue  # weekend or decorative section
        dishes: list[Dish] = []
        for dish_el in section.select(".castit-dish"):
            title = dish_el.select_one(".castit-dish__title")
            desc = dish_el.select_one(".castit-dish__desc")
            parts = [el.get_text(" ", strip=True) for el in (title, desc) if el]
            text = " ".join(p for p in parts if p)
            if text and not day_key(text):
                dishes.append(Dish(text))
        if dishes:
            days[key] = dishes
    return days
