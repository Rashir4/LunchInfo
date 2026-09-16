"""at PARK — weekly lunch server-rendered on /meny/lunch/.

Block div.row.row-2 holds two columns: the weekday menu as <h3>DAY</h3>
followed by dish <p> elements, and a vegetarian column with day-range headers
("MÅNDAG - ONSDAG", "TORSDAG - FREDAG") under an "VEGETARISK ALTERNATIV"
heading, then static klassiker/dessert sections (with inline prices) that are
skipped. Day-name casing varies week to week; occasionally two dishes share
one <p> separated by a double <br>.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="at-park",
    name="at PARK",
    address="Kungsportsavenyn 36, 411 36 Göteborg",
    url="https://atpark.se/",
    menu_url="https://atpark.se/meny/lunch/",
    walk_minutes=5,
    cuisine="Modern svenskt",
    price="169 kr",
    lunch_hours="Mån–fre 11.30–14.00",
)

_DAY = r"(måndag|tisdag|onsdag|torsdag|fredag)"
_SINGLE_DAY_RE = re.compile(rf"^{_DAY}$", re.IGNORECASE)
_DAY_RANGE_RE = re.compile(rf"^{_DAY}\s*[-–—]\s*{_DAY}$", re.IGNORECASE)

# Lines that are not dishes: pure prices, separators, buffet boilerplate.
_PRICED_LINE_RE = re.compile(r"\d{2,3}\s*:-")
_SEPARATOR_RE = re.compile(r"^_{3,}$")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _split_on_double_br(element) -> list[str]:
    """Split an element's text at runs of two or more <br> tags.

    Must work on the tag tree: get_text("\n", strip=True) drops whitespace-only
    strings, so consecutive <br> tags collapse into a single newline and are
    indistinguishable from a normal line break.
    """
    chunks: list[str] = []
    current: list[str] = []
    breaks = 0
    for node in element.descendants:
        if getattr(node, "name", None) == "br":
            breaks += 1
            if breaks >= 2 and current:
                chunks.append(" ".join(current))
                current = []
            continue
        if getattr(node, "name", None) is not None:
            continue  # container tag; its text arrives via its own children
        text = str(node).strip()
        if not text:
            continue
        breaks = 0
        current.append(text)
    if current:
        chunks.append(" ".join(current))
    return chunks


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")
    menu = soup.select_one("div.row.row-2") or soup
    days: dict[str, list[Dish]] = {}

    columns = menu.select("div.col-sm-6") or [menu]
    for col in columns:
        targets: list[str] = []  # day keys the following <p> dishes apply to
        veg_mode = False
        for el in col.find_all(["h2", "h3", "p"]):
            if el.name in ("h2", "h3"):
                heading = _norm(el.get_text(" ", strip=True))
                low = heading.lower()
                m = _DAY_RANGE_RE.match(heading)
                if m:
                    first, last = day_key(m.group(1)), day_key(m.group(2))
                    if first and last:
                        i, j = WEEKDAYS.index(first), WEEKDAYS.index(last)
                        targets = list(WEEKDAYS[min(i, j): max(i, j) + 1])
                    continue
                if _SINGLE_DAY_RE.match(heading):
                    dk = day_key(heading)
                    targets = [dk] if dk else []
                    continue
                if "vegetarisk" in low:
                    veg_mode = True
                    targets = list(WEEKDAYS)  # until a day-range narrows it
                    continue
                # Any other heading (klassiker, dessert, empty) ends the section.
                targets = []
                veg_mode = False
                continue

            if not targets:
                continue
            # Double <br> separates two dishes sharing one <p>.
            chunks = _split_on_double_br(el)
            for chunk in chunks:
                text = _norm(chunk.replace("\n", " "))
                if not text or _SEPARATOR_RE.match(text):
                    continue
                if _PRICED_LINE_RE.search(text):
                    continue  # klassiker/dessert-style à la carte line
                if text.lower().startswith("salladsbuffé"):
                    continue  # buffet boilerplate repeated under the menu
                for dk in targets:
                    days.setdefault(dk, []).append(
                        Dish(text, tag="veg" if veg_mode else None)
                    )

    return days
