"""Surr Lunch (Brewhouse, Gårda) — weekly menu via kvartersmenyn.se.

The restaurant's own site only links to Instagram, so we scrape the
server-rendered kvartersmenyn page. The whole week sits in the first
div.day > div.meny block: <strong>Måndag..Fredag</strong> day markers with
<br>-separated lines alternating category ("Kött"/"Fisk"/"Veg(etarisk)") and
dish. kvartersmenyn injects hidden anti-scrape junk as <i style="opacity:
0.1...">...</i> inside dish lines — all <i> elements are decomposed before
text extraction. The second div.meny (price/hours) is ignored.
"""

from __future__ import annotations


from . import _kvartersmenyn
from ..models import Dish, Restaurant
from ..utils import day_key, is_day_heading

RESTAURANT = Restaurant(
    id="surr-lunch",
    name="Surr Lunch",
    address="Åvägen 24, 412 51 Göteborg",
    url="https://www.surrarena.se/",
    menu_url="https://www.kvartersmenyn.se/rest/16891",
    walk_minutes=13,
    cuisine="Modern svenskt",
    price="129 kr",
    lunch_hours="11.30–13.30",
)

# Category marker lines -> dish tag (None = no tag).
_CATEGORIES = {
    "kött": None,
    "fisk": "fisk",
    "veg": "veg",
    "vegetarisk": "veg",
    "vegetariskt": "veg",
    "vegan": "veg",
    "veganskt": "veg",
}


def parse(html: str) -> dict[str, list[Dish]]:
    lines = _kvartersmenyn.menu_lines(html)
    if not lines:
        return {}

    days: dict[str, list[Dish]] = {}
    current: str | None = None
    tag: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        word = line.rstrip(":").lower()
        # is_day_heading also covers headings carrying a date ("Onsdag 17/9")
        # and weekend labels, which day_key deliberately maps to None.
        if is_day_heading(line):
            current = day_key(line)
            if current:
                days.setdefault(current, [])
            tag = None
            continue
        if word in _CATEGORIES:
            tag = _CATEGORIES[word]
            continue
        if current is None:
            continue
        days[current].append(Dish(line, tag=tag))
        tag = None

    return days
