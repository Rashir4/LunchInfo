"""Restaurang Mandarin — Chinese classics at Södra Vägen 51.

The lunch is a FIXED weekday rotation rather than a menu that changes each
week: the same seven numbered dishes come back every Tuesday, every Wednesday
and so on. RESTAURANT.static_menu marks that, so the card never implies the
dishes are new this week. The kitchen is closed on Mondays, so "mon" is absent.

The page is Squarespace: every weekday is its own ``div.sqs-html-content``
block whose first heading is the bare day name. Blocks without a day heading
(the "Dagens Lunch" intro, opening hours, address) are skipped outright —
walking day state across blocks would otherwise sweep the opening-hours lines
into Friday's menu.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import NO_TAG, Dish, Restaurant, classify_dish
from ..utils import exact_day_key

RESTAURANT = Restaurant(
    id="restaurang-mandarin",
    name="Restaurang Mandarin",
    address="Södra Vägen 51, 412 54 Göteborg",
    url="https://www.restaurangmandarin.com/",
    menu_url="https://www.restaurangmandarin.com/lunch1",
    walk_minutes=3,
    cuisine="Kinesiskt",
    price="119–145 kr",
    lunch_hours="tis–fre 11.00–15.00",
    static_menu=True,
)

# The multi-course plates (F, G) list their courses on following lines, each
# opening with a hyphen: "F. Tvårätters tallrik 135:-" / "-Friterade räkor…".
_COURSE = re.compile(r"^-\s*(.+)$")


def _plate(name: str, courses: list[str]) -> Dish:
    """One menu entry: a single dish, or a plate with its courses spelled out.

    A plate is tagged by its FIRST course. Letting Dish auto-classify the joined
    text would hand "Trerätters tallrik / räkor / biff / Vegetariska minivårrullar"
    a veg badge, because an explicit vegetarian label anywhere outranks position —
    right for one dish, wrong for a plate whose third course is the vegetarian
    one. An empty tag means "no badge" without a second guess at the full text.
    """
    if not courses:
        return Dish(name)
    # Tag by the FIRST course: classifying the joined text would badge a
    # three-course plate veg just because its last course is vegetarian.
    return Dish(f"{name} ({' + '.join(courses)})", tag=classify_dish(courses[0]) or NO_TAG)


def _block_lines(block) -> list[str]:
    """Visible text of one Squarespace HTML block, one line per heading/paragraph."""
    lines = []
    for el in block.find_all(["h1", "h2", "h3", "h4", "h5", "p"]):
        text = re.sub(r"\s+", " ", el.get_text(" ")).strip()
        if text:
            lines.append(text)
    return lines


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")

    days: dict[str, list[tuple[str, list[str]]]] = {}
    for block in soup.select("div.sqs-html-content"):
        lines = _block_lines(block)
        if not lines:
            continue
        key = exact_day_key(lines[0])
        if key is None:
            continue  # intro text, opening hours, address — not a menu block

        entries: list[tuple[str, list[str]]] = []
        for line in lines[1:]:
            course = _COURSE.match(line)
            if course and entries:
                entries[-1][1].append(course.group(1))
            else:
                entries.append((line, []))
        if entries:
            days.setdefault(key, []).extend(entries)

    return {
        day: [_plate(name, courses) for name, courses in entries]
        for day, entries in days.items()
    }
