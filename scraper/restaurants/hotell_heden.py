"""Hotell Heden — weekly lunch from hotellheden.se/ata/lunch/.

Server-rendered WordPress page. CAUTION: heading id attributes are stale
copy-paste leftovers (Monday's h3 may carry id="h-tisdag"), so we match on
visible heading text only, never on ids/anchors. Day-name casing is
inconsistent ("MÅndag", "fredag"). "Veckans vegetariska" and "Veckans soppa"
sections precede Monday and apply to every weekday.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="hotell-heden",
    name="Hotell Heden",
    address="Sten Sturegatan 1, 411 39 Göteborg",
    url="https://hotellheden.se",
    menu_url="https://hotellheden.se/ata/lunch/",
    walk_minutes=10,
    cuisine="Husmanskost",
    price="135 kr",
    lunch_hours="11.30–13.30",
)

# Sections before Monday whose single dish applies to the whole week.
_WEEKLY_SECTIONS = ("veckans vegetariska", "veckans soppa")

# Boilerplate fragments that must never become dish text.
# Boilerplate lines to drop. Matched as a PREFIX, not a substring: a dish like
# "Fläskfilé ..., inkl. sallad och bröd" or "prisbelönt korv" must survive.
_BOILERPLATE_PREFIXES = (
    "inkl.", "avhämtning", "öppet för lunch", "fråga oss", "pris",
    "senior", "serveras vardagar", "alla luncher", "i priset ingår",
)


def _dish_lines(heading) -> list[str]:
    """Text lines of the consecutive <p> siblings following a heading."""
    lines: list[str] = []
    for sib in heading.find_next_siblings():
        if sib.name in ("h1", "h2", "h3", "h4", "hr"):
            break  # next section starts here
        if sib.name != "p":
            continue  # spacer/divider blocks sit between dish paragraphs
        for line in sib.get_text("\n").split("\n"):
            line = line.strip()
            if line and not line.lower().startswith(_BOILERPLATE_PREFIXES):
                lines.append(line)
    return lines


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")

    days: dict[str, list[Dish]] = {}
    weekly: list[Dish] = []

    for h in soup.select("h3.wp-block-heading"):
        text = h.get_text(strip=True)
        low = text.casefold().rstrip(":").strip()
        if low in _WEEKLY_SECTIONS:
            label = text[:1].upper() + text[1:]
            tag = "veg" if "vegetariska" in low else None
            weekly.extend(
                Dish(f"{label}: {line}", tag=tag) for line in _dish_lines(h)
            )
            continue
        key = day_key(text)
        if key:
            # Extend, never replace: a day is sometimes split over two headings.
            days.setdefault(key, []).extend(Dish(line) for line in _dish_lines(h))

    days = {d: dishes for d, dishes in days.items() if dishes}
    if weekly:
        for d in WEEKDAYS:
            if d in days:
                days[d].extend(Dish(w.text, tag=w.tag) for w in weekly)
    return days
