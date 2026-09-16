"""Traktör | Mikael Sande — French-Swedish lunch kitchen in Johanneberg.

https://traktormikaelsande.se/dagens-lunch/ is WordPress + WPBakery, server-
rendered. One dish per weekday lives in a div carrying both the marker class
``dagens-lunch-ikon`` and a bare Swedish day class (``mandag`` … ``fredag``);
Mondays the restaurant is closed and that div just reads "Stängt".

Two blocks apply to the whole week and are appended to every open day:
"Veckans vegetariska" (tagged veg — the kitchen's own label, the dish name
alone rarely gives it away) and "Varje vecka serveras även" (the two house
classics), which sits in a ``dagens-lunch-ikon`` div with no day class.

The week number is its own element (``div.vecka-nr``), so detect_week() flags
a menu that has not been updated yet.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant

RESTAURANT = Restaurant(
    id="traktor-mikael-sande",
    name="Traktör Mikael Sande",
    address="Viktor Rydbergsgatan 46, 412 57 Göteborg",
    url="https://traktormikaelsande.se/",
    menu_url="https://traktormikaelsande.se/dagens-lunch/",
    walk_minutes=8,
    cuisine="Husmanskost",
    price="159 kr (take-away 139 kr)",
    lunch_hours="Tis–fre 11.00–15.00",
)

# The day classes are unaccented and lowercase in the markup.
_DAY_CLASSES = {
    "mandag": "mon",
    "tisdag": "tue",
    "onsdag": "wed",
    "torsdag": "thu",
    "fredag": "fri",
}

# A closed day is spelled out in the same slot a dish would occupy.
_CLOSED = re.compile(r"^st[äa]ngt\b", re.IGNORECASE)

_VEG_HEADING = re.compile(r"veckans\s+vegetariska", re.IGNORECASE)


def _lines(block) -> list[str]:
    texts = (p.get_text(" ", strip=True) for p in block.find_all("p"))
    return [t for t in texts if t and not _CLOSED.match(t)]


def _weekly_veg(soup) -> list[Dish]:
    """Dishes under the "Veckans vegetariska" heading, tagged veg."""
    for heading in soup.find_all(["h2", "h3", "h4", "h5"]):
        if not _VEG_HEADING.search(heading.get_text(" ", strip=True)):
            continue
        dishes = []
        for sib in heading.find_next_siblings():
            if sib.name in ("h1", "h2", "h3", "h4", "h5"):
                break  # the next section starts here
            if sib.name == "p":
                text = sib.get_text(" ", strip=True)
                if text:
                    dishes.append(Dish(text, tag="veg"))
        return dishes
    return []


def detect_week(raw: str) -> int | None:
    """ISO week the menu block is labelled with, or None if unlabelled."""
    el = BeautifulSoup(raw, "lxml").select_one("div.vecka-nr")
    if el is None:
        return None
    m = re.search(r"\b(\d{1,2})\b", el.get_text(" ", strip=True))
    if not m:
        return None
    week = int(m.group(1))
    return week if 1 <= week <= 53 else None


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")

    days: dict[str, list[Dish]] = {}
    every_day: list[Dish] = []
    for block in soup.select("div.dagens-lunch-ikon"):
        classes = set(block.get("class") or [])
        day = next((_DAY_CLASSES[c] for c in classes if c in _DAY_CLASSES), None)
        dishes = [Dish(text) for text in _lines(block)]
        if not dishes:
            continue  # a closed day
        if day:
            days.setdefault(day, []).extend(dishes)
        else:
            every_day.extend(dishes)  # "Varje vecka serveras även"

    if not days:
        return {}

    every_day = _weekly_veg(soup) + every_day
    for day in days:
        # Fresh Dish objects per day: main.py's dedupe may replace entries, and
        # sharing one instance across days would let that leak between them.
        days[day].extend(Dish(d.text, tag=d.tag) for d in every_day)
    return days
