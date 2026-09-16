"""Restaurang VKM (Världskulturmuseet) — scraped via kvartersmenyn.se.

The restaurant's own one-page site has no weekly menu, so the menu comes from
https://www.kvartersmenyn.se/rest/17034. The whole week sits in the first
div.day > div.meny: day names as <strong> (no Måndag — closed Mondays;
Lördag/Söndag are buffet notices, skipped), lines separated by <br>.
Within a day, lines alternate category label ("Kött"/"Fisk"/"Veg"/"Vegetarisk")
then dish text, which may wrap onto a following line — so lines between labels
are joined into one dish. Kvartersmenyn injects hidden anti-scrape junk as
<i style="opacity: 0.1...">pogre</i> inside dish lines; all <i> elements are
dropped before text extraction.
"""

from __future__ import annotations

import re


from . import _kvartersmenyn
from ..models import Dish, Restaurant
from ..utils import day_key, is_day_heading

RESTAURANT = Restaurant(
    id="restaurang-vkm",
    name="Restaurang VKM",
    address="Södra Vägen 54 (Världskulturmuseet), 412 54 Göteborg",
    url="https://www.vinkulturochmat.se",
    menu_url="https://www.kvartersmenyn.se/rest/17034",
    walk_minutes=8,
    cuisine="Varierat",
    price="149 kr",
    lunch_hours="Tis–fre 11.00–14.30 (stängt måndagar)",
)

# Category label on its own line: "Kött", "Fisk", "Veg", "Vegetarisk", ...
_CATEGORY_RE = re.compile(r"^(kött|fisk|veg|vegetarisk|vegansk|vegan)\s*:?\s*$", re.IGNORECASE)

_CATEGORY_TAGS = {"fisk": "fisk", "veg": "veg", "vegetarisk": "veg", "vegansk": "veg", "vegan": "veg"}


def parse(raw: str) -> dict[str, list[Dish]]:
    lines = _kvartersmenyn.menu_lines(raw)
    if not lines:
        return {}

    days: dict[str, list[Dish]] = {}
    day: str | None = None
    tag: str | None = None
    acc: list[str] = []  # accumulated lines of the current (possibly wrapped) dish

    def flush() -> None:
        nonlocal acc
        if day and acc:
            days.setdefault(day, []).append(Dish(" ".join(acc), tag=tag))
        acc = []

    for line in lines:
        line = line.strip()
        if not line:
            flush()
            continue
        if is_day_heading(line):
            flush()
            day = day_key(line)  # None for Lördag/Söndag -> their lines are skipped
            tag = None
            continue
        m = _CATEGORY_RE.match(line)
        if m:
            flush()
            tag = _CATEGORY_TAGS.get(m.group(1).lower())
            continue
        if day:
            acc.append(line)
    flush()
    return days
