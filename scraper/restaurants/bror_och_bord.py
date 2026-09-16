"""Bror och Bord — breakfast-and-lunch kitchen on Bohusgatan, by Heden.

The whole site is one WordPress page and the lunch menu is its front page, so
url and menu_url are the same. The menu block is a run of paragraphs: a
``<p><strong>Måndag</strong></p>`` heading, then one paragraph whose dishes are
separated by ``<br>``, repeated Monday–Friday and closed by an ``<hr>`` before
the price footnote. Parsing therefore walks paragraphs in document order and
stops at that rule, rather than trusting the theme's class names.

The heading labels its own week ("Lunchmeny vecka – 38"), which detect_week
reads so a menu left over from last week gets flagged instead of shown as new.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import exact_day_key

RESTAURANT = Restaurant(
    id="bror-och-bord",
    name="Bror och Bord",
    address="Bohusgatan 15, 411 39 Göteborg",
    url="https://brorochbord.se/",
    menu_url="https://brorochbord.se/",
    walk_minutes=15,
    cuisine="Husmanskost",
    price="135 kr",
    lunch_hours="11.00–14.30",
)

# The heading spells the week with an en dash ("vecka – 38"), which the shared
# week matcher does not allow between the word and the number.
_WEEK_RE = re.compile(r"lunchmeny\s*vecka\s*[–—-]*\s*(\d{1,2})\b", re.IGNORECASE)


def _menu_block(soup: BeautifulSoup):
    """The smallest element holding the whole Mon–Fri run, or None."""
    blocks = [
        el for el in soup.find_all(["div", "section", "article"])
        if sum(1 for s in el.find_all("strong") if exact_day_key(s.get_text())) >= 5
    ]
    if not blocks:
        return None
    # Every ancestor of the menu matches; the smallest is the menu itself.
    return min(blocks, key=lambda el: len(el.get_text()))


def parse(raw: str) -> dict[str, list[Dish]]:
    block = _menu_block(BeautifulSoup(raw, "lxml"))
    if block is None:
        return {}

    days: dict[str, list[Dish]] = {}
    current: str | None = None
    for el in block.find_all(["p", "hr"]):
        if el.name == "hr":
            break  # end of the menu; the price footnote follows
        key = exact_day_key(el.get_text())
        if key:
            current = key
            days.setdefault(current, [])
            continue
        if current is None:
            continue  # intro text above Monday
        for br in el.find_all("br"):
            br.replace_with("\n")
        for line in el.get_text("\n").split("\n"):
            text = line.strip()
            if text:
                days[current].append(Dish(text))

    return {day: dishes for day, dishes in days.items() if dishes}


def detect_week(raw: str) -> int | None:
    """The ISO week the menu heading claims, or None when it does not say."""
    m = _WEEK_RE.search(BeautifulSoup(raw, "lxml").get_text(" "))
    if not m:
        return None
    week = int(m.group(1))
    return week if 1 <= week <= 53 else None
