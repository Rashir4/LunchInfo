"""Restaurang C — lunch restaurant at Carlanderska sjukhuset (Carlandersparken).

The weekly menu on crestaurang.se/meny/ is server-rendered inside <main>:
ALL-CAPS weekday headings, each followed by ALL-CAPS dish titles with a
mixed-case garnish line below ("Bakpotatis — Smetana — Mangosalsa").
The markup around dish titles is inconsistent (<strong> is sometimes
missing), so we parse the text lines of <main> anchored on day headings.
Trailing "veckans sallad" / "veckans vegetarisk(a)" sections are weekly
dishes and go into every weekday's list.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="restaurang-c",
    name="Restaurang C",
    address="Carlandersparken 21",
    url="https://crestaurang.se/",
    menu_url="https://crestaurang.se/meny/",
    walk_minutes=9,
    cuisine="Varierat",
    price="155 kr",
    lunch_hours="11.00–14.00",
)

# A line that is ONLY a weekday name (optionally followed by a date / time
# digits, but no other letters) — so "måndag-fredag 11.00-14.00" is NOT a
# day heading here while "MÅNDAG" or "Måndag 15/9" is.
_DAY_LINE = re.compile(
    r"^\s*(måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag)\b[\s\d:./–—-]*$",
    re.IGNORECASE,
)

_WEEKLY_HEADING = re.compile(r"^\s*veckans\b", re.IGNORECASE)


def _is_title(line: str) -> bool:
    """Dish titles are set in ALL CAPS (e.g. 'PULLED PORK')."""
    return line.upper() == line and line.lower() != line


def _weekly_label(heading: str) -> str:
    low = heading.lower()
    if "veg" in low:  # the site spells it "VEGERTARISK" some weeks
        return "Veckans vegetariska"
    if "sallad" in low:
        return "Veckans sallad"
    return "Veckans"


def _join(title: str, desc_parts: list[str]) -> str:
    desc = " ".join(desc_parts).strip()
    desc = re.sub(r"\s*—\s*", " — ", desc).strip(" —")
    if not desc:
        return title
    return f"{title} — {desc}"


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")
    root = soup.find("main") or soup
    lines = [ln.strip() for ln in root.get_text("\n").splitlines() if ln.strip()]

    days: dict[str, list[Dish]] = {}
    weekly: list[Dish] = []

    day: str | None = None
    title: str | None = None
    desc: list[str] = []
    weekly_label: str | None = None  # set while inside a "veckans ..." section

    def flush() -> None:
        nonlocal title, desc
        if title:
            text = _join(title, desc)
            if weekly_label:
                weekly.append(Dish(f"{weekly_label}: {text}"))
            elif day:
                days.setdefault(day, []).append(Dish(text))
        title, desc = None, []

    for line in lines:
        if _DAY_LINE.match(line):
            flush()
            weekly_label = None
            day = day_key(line)  # None for weekend headings
            continue
        if _WEEKLY_HEADING.match(line):
            flush()
            weekly_label = _weekly_label(line)
            day = None
            continue
        if weekly_label:
            # first line of the section is the dish name, the rest garnish
            if title is None:
                title = line
            else:
                desc.append(line)
            continue
        if day is None:
            continue  # intro boilerplate before the first day heading
        if _is_title(line):
            flush()
            title = line
        elif title is not None:
            desc.append(line)
    flush()

    for dish in weekly:
        for key in days:
            days[key].append(dish)
    return days
