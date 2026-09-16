"""MATSMAK — Södra Gårda lunch kitchen (WordPress + WPBakery, server-rendered).

The weekly menu on https://matsmak.se/dagens-lunch/ is one <p> per weekday:
<p><strong>MÅNDAG –</strong><br/>KÖTT: ...<br/>FISK: ...<br/>VEG: ...</p>
The <strong> day header sometimes carries promo text ("ONSDAG – ~VI BJUDER
PÅ PAJ...~"); dish lines are <br>-separated and keep their category prefix
(KÖTT:/FISK:/VEG:/PASTA:). Only the current week is published.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import day_key, is_day_heading

RESTAURANT = Restaurant(
    id="matsmak",
    name="MATSMAK",
    address="Drakegatan 1, 412 50 Göteborg",
    url="https://matsmak.se/",
    menu_url="https://matsmak.se/dagens-lunch/",
    walk_minutes=19,
    cuisine="Husmanskost",
    price="139 kr (takeaway 129 kr)",
    lunch_hours="11.00–13.30",
)


def parse(html: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(html, "lxml")
    days: dict[str, list[Dish]] = {}

    # A weekday paragraph is a <p> whose leading <strong> starts with the
    # uppercase Swedish day name ("MÅNDAG –"). This is unique on the page:
    # the static "VARJE DAG PÅ LUNCHMENYN" block uses <b>, not day names.
    for p in soup.find_all("p"):
        strong = p.find("strong")
        if strong is None:
            continue
        key = day_key(strong.get_text(strip=True))
        if key is None:
            continue

        for br in p.find_all("br"):
            br.replace_with("\n")
        lines = [line.strip() for line in p.get_text().split("\n")]
        dishes = []
        for line in lines:
            if not line or is_day_heading(line):
                continue  # skip the day header (incl. any trailing promo text)
            dishes.append(Dish(line))
        if dishes:
            days[key] = dishes

    return days
