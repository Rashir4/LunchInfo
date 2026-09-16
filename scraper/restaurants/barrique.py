"""Barrique — Wix site; lunch served Tuesday-Friday only (no Monday lunch).

The /lunch page is server-rendered and embeds the menu CMS collection in
<script type="application/json" id="wix-warmup-data"> under
recordsByCollectionId -> "Import1". Records carry:
  ratt        - Swedish dish name incl. price ("Helstekt fläskfilé 149 KR")
  forklaring  - Swedish description
  rattnummer  - slot: 1 = tue/wed main, 2 = standing meatball classic,
                3 = fish, 4 = vegetarian, 5 = thu/fri main,
                6-9 = "Det lilla extra" desserts tue..fri
  vecka       - week label ("v 38"), sparsely populated
  _publishDate - set when the week's menu is published (Mondays)
The collection holds several weeks: per slot we prefer a record matching the
current ISO week when vecka is present, otherwise the most recently published.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import current_week, week_in_text

RESTAURANT = Restaurant(
    id="barrique",
    name="Barrique",
    address="Berzeliigatan 18, 411 36 Göteborg",
    url="https://www.barrique.nu",
    menu_url="https://www.barrique.nu/lunch",
    walk_minutes=6,
    cuisine="Modern svenskt",
    price="149–179 kr",
    lunch_hours="Tis–fre 11.30–14.00 (ingen lunch måndagar)",
)

# Which weekdays each menu slot (rattnummer) applies to.
_SLOT_DAYS = {
    1: ("tue", "wed"),               # tue/wed main
    2: ("tue", "wed", "thu", "fri"),  # standing meatball classic
    3: ("tue", "wed", "thu", "fri"),  # weekly fish
    4: ("tue", "wed", "thu", "fri"),  # weekly vegetarian
    5: ("thu", "fri"),               # thu/fri main
    6: ("tue",),                     # desserts ("Det lilla extra")
    7: ("wed",),
    8: ("thu",),
    9: ("fri",),
}
_DESSERT_SLOTS = {6, 7, 8, 9}
_SLOT_TAGS = {3: "fisk", 4: "veg"}
# Menu-like order within a day: the day's main first, then the standing
# classics/fish/veg, desserts last.
_SLOT_ORDER = {1: 0, 5: 0, 2: 1, 3: 2, 4: 3, 6: 9, 7: 9, 8: 9, 9: 9}


def _find_records(node) -> dict | None:
    """Recursively locate 'recordsByCollectionId' in the warmup-data JSON."""
    if isinstance(node, dict):
        if "recordsByCollectionId" in node:
            return node["recordsByCollectionId"]
        for value in node.values():
            found = _find_records(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_records(value)
            if found is not None:
                return found
    return None


def _publish_key(record: dict) -> str:
    date = record.get("_publishDate") or record.get("_updatedDate") or ""
    if isinstance(date, dict):  # e.g. {"$date": "..."}
        date = next(iter(date.values()), "")
    return str(date)


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")
    script = soup.find("script", id="wix-warmup-data")
    if script is None or not script.string:
        return {}
    records_by_collection = _find_records(json.loads(script.string)) or {}
    records = []
    for collection_id, recs in records_by_collection.items():
        if collection_id.lower().startswith("import"):
            values = recs.values() if isinstance(recs, dict) else recs
            records.extend(r for r in values if isinstance(r, dict))
    if not records:
        return {}

    _, week = current_week()

    # Bucket records per menu slot, then pick the freshest (preferring an
    # explicit current-week label over publish date).
    slots: dict[int, list[dict]] = {}
    for rec in records:
        try:
            slot = int(rec.get("rattnummer"))
        except (TypeError, ValueError):
            continue
        if slot in _SLOT_DAYS and (rec.get("ratt") or "").strip():
            slots.setdefault(slot, []).append(rec)

    days: dict[str, list[Dish]] = {}
    for slot, recs in sorted(slots.items(), key=lambda kv: (_SLOT_ORDER.get(kv[0], 5), kv[0])):
        current = [r for r in recs if week_in_text(str(r.get("vecka") or "")) == week]
        pick = max(current or recs, key=_publish_key)
        name = pick["ratt"].strip()
        # A placeholder like "." marks the slot as intentionally empty this
        # week (e.g. a holiday) — omit it rather than fall back to old data.
        if not re.search(r"\w", name):
            continue
        desc = (pick.get("forklaring") or "").strip()
        text = f"{name} – {desc}" if desc else name
        if slot in _DESSERT_SLOTS:
            text = f"Det lilla extra: {text}"
        for day in _SLOT_DAYS[slot]:
            days.setdefault(day, []).append(Dish(text, tag=_SLOT_TAGS.get(slot)))

    return days
