"""Ölstugan Tullen Avenyn — Kungsportsavenyen 32.

olstugan.se is a Next.js site: the weekly lunch menu ("Lunchmeny V.NN")
is embedded in the page body as React flight data — JSON string chunks
pushed via self.__next_f.push([1, "..."]) — so plain HTML fetching works.
parse() decodes the chunks, extracts the "menus" JSON array and reads the
menu with menuType == "Lunch".
"""

from __future__ import annotations

import json
import re

from ..models import Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="olstugan-tullen-avenyn",
    name="Ölstugan Tullen Avenyn",
    address="Kungsportsavenyen 32",
    url="https://olstugan.se/sv/restaurants/avenyn",
    menu_url="https://olstugan.se/sv/restaurants/avenyn",
    walk_minutes=7,
    cuisine="Husmanskost",
    price="135 kr",
    lunch_hours="11.00–14.45",
)

_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')

# Categories that repeat every weekday vs. boilerplate about what's included.
_EVERY_DAY_PREFIX = "SERVERAS"  # "SERVERAS VARJE DAG"


def _flight_payload(raw: str) -> str:
    """Concatenate the decoded __next_f string chunks into one stream."""
    return "".join(json.loads(chunk) for chunk in _PUSH_RE.findall(raw))


def _balanced_array(text: str, start: int) -> str:
    """Return the JSON array starting at text[start] ('['), string-aware."""
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced JSON array in flight data")


def _menus(payload: str) -> list[dict]:
    menus: list[dict] = []
    for m in re.finditer(r'"menus":\s*\[', payload):
        try:
            menus.extend(json.loads(_balanced_array(payload, m.end() - 1)))
        except ValueError:
            continue
    return [m for m in menus if isinstance(m, dict)]


def _dish(item: dict) -> Dish:
    name = (item.get("name") or "").strip()
    desc = (item.get("description") or "").strip()
    return Dish(f"{name} – {desc}" if desc else name)


def parse(raw: str) -> dict[str, list[Dish]]:
    lunch = next(
        (m for m in _menus(_flight_payload(raw)) if m.get("menuType") == "Lunch"),
        None,
    )
    if lunch is None:
        raise ValueError("no lunch menu found in page data")

    days: dict[str, list[Dish]] = {}
    every_day: list[Dish] = []
    for category in lunch.get("categories", []):
        name = (category.get("name") or "").strip()
        items = [_dish(it) for it in category.get("items", []) if it.get("name")]
        key = day_key(name)
        if key:
            days.setdefault(key, []).extend(items)
        elif name.upper().startswith(_EVERY_DAY_PREFIX):
            every_day = items
        # "INGÅR ALLTID" (what the price includes) is boilerplate — skipped.

    for dishes in days.values():
        dishes.extend(every_day)
    return days
