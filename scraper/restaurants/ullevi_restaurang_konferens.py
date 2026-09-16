"""Ullevi Restaurang & Konferens — weekly lunch buffet menu.

Server-rendered WordPress page (needs a browser User-Agent, which fetch_html
sends). The whole menu sits in the single <div class="text white"> container:
first <p><strong>Vecka NN</strong></p>, then one <p> per weekday shaped as
<strong>Måndag<br/></strong>Dish 1<br/>Dish 2. Fuchsia-colored <span> lines are
dessert promos and are dropped. Trailing blocks "Veckans vegetariska:" and
"Veckans sallad:" apply to every weekday; "Alltid på meny:" (static köttbullar
with its own price) and the senior-discount note are skipped.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="ullevi-restaurang-konferens",
    name="Ullevi Restaurang & Konferens",
    address="Paradentrén, Ullevi (vån 2), 411 40 Göteborg",
    url="https://www.ullevikonferens.se/",
    menu_url="https://www.ullevikonferens.se/restaurang/lunch/",
    walk_minutes=16,
    cuisine="Husmanskost",
    price="129 kr (buffé)",
    lunch_hours="11.00–13.30",
)


def parse(html: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one("div.text.white")
    if container is None:
        return {}

    # Dessert/promo lines are styled <span style="color: fuchsia"> — not dishes.
    for span in container.select('span[style*="fuchsia"]'):
        span.decompose()

    days: dict[str, list[Dish]] = {}
    weekly: list[Dish] = []  # "Veckans vegetariska" / "Veckans sallad"

    for p in container.find_all("p"):
        lines = [ln.strip() for ln in p.get_text("\n").split("\n")]
        lines = [ln for ln in lines if ln]
        if not lines:
            continue
        label = lines[0].replace("\xa0", " ").lower()
        key = day_key(lines[0])
        if key:
            # Extend, never replace: a day's dishes are sometimes split across
            # two <p> elements, and assignment would keep only the last block.
            days.setdefault(key, []).extend(Dish(ln) for ln in lines[1:])
        elif label.startswith("veckans vegetariska"):
            weekly.extend(Dish(ln, tag="veg") for ln in lines[1:])
        elif label.startswith("veckans sallad"):
            weekly.extend(Dish(ln) for ln in lines[1:])
        # else: "Vecka NN" header, "Alltid på meny", "Seniorsrabatt" — skip.

    if weekly:
        for key in list(days) or list(WEEKDAYS):
            days.setdefault(key, []).extend(Dish(d.text, tag=d.tag) for d in weekly)
    return days
