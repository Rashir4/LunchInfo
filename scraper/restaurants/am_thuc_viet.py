"""Am Thuc Viet (Ẩm Thực Việt) — Vietnamese kitchen on Södra Vägen.

The lunch is a FIXED weekday rotation, not a menu that changes each week: the
same five numbered dishes come back every Tuesday, every Wednesday and so on,
and the page carries no week number. RESTAURANT.static_menu says so, since
"veckans lunch" would otherwise overpromise. Mondays are closed, so "mon" is
absent.

https://www.amthucviet.se/meny is Squarespace. Both menus (à la carte and
lunch) are server-rendered into the page; the lunch one is the
``div.menu-section`` whose ``.menu-section-title`` starts with "Lunch" — its
tab is hidden with CSS, not fetched by JS. Inside, every row is a
``div.menu-item``: a bare weekday title opens a day, and the day's dishes are
the numbered ones ("1. Bún Chả Giò Thịt Gà").

Only numbered rows are taken. The unnumbered ones are not part of the 135 kr
rotation: drink add-ons, an allergy note, and a standing "Erbjuds alltid Phở
…155/160/170 kr" line offering a choice of vegetarian, chicken or beef broth —
which is priced apart from the lunch and too ambiguous to badge honestly.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import exact_day_key

RESTAURANT = Restaurant(
    id="am-thuc-viet",
    name="Am Thuc Viet",
    address="Södra Vägen 11, 411 35 Göteborg",
    url="https://www.amthucviet.se/",
    menu_url="https://www.amthucviet.se/meny",
    walk_minutes=12,
    cuisine="Vietnamesiskt",
    price="135 kr",
    lunch_hours="Tis–fre 11.00–14.30",
    static_menu=True,
)

# "1. Bún Chả Giò Thịt Gà", "2.Thịt Bò Xào Xả", "15-. Đậu Xào Xả" — the space
# after the number and the separator itself are both inconsistent on the page.
_NUMBERED = re.compile(r"^\d+\s*[-.)]")


def _field(item, cls: str) -> str:
    el = item.select_one(f".{cls}")
    return el.get_text(" ", strip=True) if el else ""


def _lunch_section(soup):
    for section in soup.select("div.menu-section"):
        title = _field(section, "menu-section-title")
        if title.casefold().startswith("lunch"):
            return section
    return None


def parse(raw: str) -> dict[str, list[Dish]]:
    section = _lunch_section(BeautifulSoup(raw, "lxml"))
    if section is None:
        return {}

    days: dict[str, list[Dish]] = {}
    current: str | None = None
    for item in section.select("div.menu-item"):
        title = _field(item, "menu-item-title")
        if not title:
            continue
        key = exact_day_key(title)
        if key:
            current = key
            continue
        if current is None or not _NUMBERED.match(title):
            continue
        description = _field(item, "menu-item-description")
        days.setdefault(current, []).append(
            Dish(f"{title} – {description}" if description else title)
        )

    return {day: dishes for day, dishes in days.items() if dishes}
