"""Aptitgården (Gårda) — weekly lunch from the Elementor-built one-pager.

The menu lives in the container with id="vecko-meny": each weekday is an
<h2 class="elementor-heading-title"> whose text is exactly the day name,
and the dishes are the <p> elements of the next-sibling
div.elementor-widget-text-editor widget (5-6 per day, the last two being
recurring quesadilla/cevapcici items listed per day on the site).
Elementor data-id attributes are build-specific and never used.
Price is not published on the official site (130 kr per kvartersmenyn).
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import exact_day_key

RESTAURANT = Restaurant(
    id="aptitgarden",
    name="Aptitgården",
    address="Vädursgatan 5, 412 50 Göteborg",
    url="https://aptitgarden.com/sv/",
    menu_url="https://aptitgarden.com/sv/#vecko-meny",
    walk_minutes=18,
    cuisine="Husmanskost",
    price="130 kr",
    lunch_hours="10.30–14.00",
)


def parse(html: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(html, "lxml")
    section = soup.find(id="vecko-meny")
    if section is None:
        return {}

    days: dict[str, list[Dish]] = {}
    for h2 in section.select("h2.elementor-heading-title"):
        # Only bare day names ("Måndag"), not e.g. the "Vecka NN" heading.
        key = exact_day_key(h2.get_text(strip=True))
        if not key:
            continue
        widget = h2.find_parent("div", class_="elementor-widget-heading")
        if widget is None:
            continue
        # Walk siblings one at a time and stop at the next day's heading: a
        # plain find_next_sibling(class=...) would skip over it and attribute
        # the following day's dishes to this one.
        editor = None
        for sibling in widget.find_next_siblings("div"):
            classes = sibling.get("class") or []
            if "elementor-widget-heading" in classes:
                break
            if "elementor-widget-text-editor" in classes:
                editor = sibling
                break
        if editor is None:
            continue
        dishes = [
            Dish(t)
            for p in editor.select("p")
            if (t := p.get_text(" ", strip=True))
        ]
        if dishes:
            days[key] = dishes
    return days
