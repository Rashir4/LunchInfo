"""Gaby's — lunch restaurant at Jacy'z Hotel, Gårda (WordPress/Avada, server-rendered).

The weekly menu on the hotel page is an "autolunch" widget rendered into the
static HTML: div.autolunch-menu holds a flat sequence of
p.autolunch-heading (section header) / p.autolunch-item (dish) elements.
Day headings are Swedish (Måndag..Fredag); earlier revisions of the page used
English day names in span[font-size:18px] headers, so both are tolerated.
Non-day sections ("Green Kitchen", "Poke Bowl – 165 SEK / pers.", "Salad of
the week") are standing weekly dishes added to every open weekday. A day whose
only item is "Stängt" (closed) is omitted.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="gabys",
    name="Gaby's",
    address="Drakegatan 10, 412 50 Göteborg",
    url="https://jacyzhotel.com/restauranger-goteborg/gabys/",
    menu_url="https://jacyzhotel.com/restauranger-goteborg/gabys/",
    walk_minutes=21,
    cuisine="Modern svenskt",
    price="145 kr (poke bowl 165 kr)",
    lunch_hours="11.00–13.30",
)

_ENGLISH_DAYS = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
}

_PRICE_RE = re.compile(r"[–-]?\s*(\d{2,3})\s*SEK.*$", re.IGNORECASE)


def _any_day_key(text: str) -> str | None:
    """Day key from a Swedish or English day heading."""
    key = day_key(text)
    if key:
        return key
    first = (text or "").strip().split()[:1]
    return _ENGLISH_DAYS.get(first[0].lower()) if first else None


def _is_heading(p) -> bool:
    if "autolunch-heading" in (p.get("class") or []):
        return True
    # Older markup: header <p> wraps a span styled with font-size: 18px.
    span = p.find("span", style=True)
    return bool(span and "font-size: 18px" in span["style"])


def parse(html: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(html, "lxml")
    container = (
        soup.select_one("div.autolunch-menu")
        or soup.select_one("div.fusion-text.larger-p-desktop")
    )
    if container is None:
        return {}

    per_day: dict[str, list[str]] = {}
    weekly: list[str] = []
    current: str | None = None  # day key, or a weekly section label

    for p in container.find_all("p"):
        text = p.get_text(" ", strip=True)
        if not text:
            continue
        if _is_heading(p):
            key = _any_day_key(text)
            if key:
                current = key
                per_day.setdefault(key, [])
            else:
                # Weekly section: keep a short label, move any price into it.
                label = text
                m = _PRICE_RE.search(label)
                if m:
                    label = f"{label[: m.start()].strip()} ({m.group(1)} kr)"
                current = f"weekly:{label}"
            continue
        if current is None or text.casefold().rstrip(".") == "stängt":
            continue
        if current.startswith("weekly:"):
            weekly.append(f"{current[len('weekly:'):]}: {text}")
        else:
            per_day[current].append(text)

    days: dict[str, list[Dish]] = {}
    for key, dishes in per_day.items():
        if not dishes:  # closed day ("Stängt") — omit entirely
            continue
        days[key] = [Dish(t) for t in dishes] + [Dish(t) for t in weekly]
    return days
