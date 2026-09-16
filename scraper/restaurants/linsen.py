"""Restaurang & Café Linsen — EDIT-huset, Chalmers Johanneberg.

The weekly menu is server-rendered on the cafe-linsen.se front page (Next.js):
one rich-text card per weekday, each carrying "Meny V.nn", a day heading like
"Måndag 14/09–2026", and the dishes in Swedish immediately followed by their
English translations. parse() anchors on the day headings, keeps the Swedish
lines and drops the English duplicates.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import day_key, week_in_text

RESTAURANT = Restaurant(
    id="linsen",
    name="Restaurang & Café Linsen",
    address="Hörsalsvägen 11 (EDIT-huset)",
    url="https://cafe-linsen.se",
    menu_url="https://cafe-linsen.se/",
    walk_minutes=14,
    cuisine="Varierat",
)

# Words that only occur in the English translations of this menu.
_EN_RE = re.compile(
    r"\b(with|and|or|of|the|today'?s?|chicken|pork|beef|salmon|shrimp|sauce|"
    r"potato(?:es)?|rice|cheese|peas|lemon|parsley|onions?|corn|beans?|soup|"
    r"plate|salad|noodles|mushrooms?|vegetarian|arugula|minced|breaded|seared|"
    r"catch|roasted|baked|fried|stir|cold|green|day)\b",
    re.IGNORECASE,
)

# Swedish giveaways: å/ä/ö, or common Swedish menu words.
_SV_RE = re.compile(
    r"[åäöÅÄÖ]|\b(med|och|eller|kyckling|fisk|lax|potatis|gryta|vegetarisk|"
    r"dagens|stekt|rostad|kokt|hemmagjorda|bullar|soppa|nudlar|tallrik|vego|"
    r"svamp|kantareller)\b",
    re.IGNORECASE,
)


def _lang(text: str) -> str:
    sv = bool(_SV_RE.search(text))
    en = bool(_EN_RE.search(text))
    if sv and en:
        return "mixed"
    if en:
        return "en"
    if sv:
        return "sv"
    return "neutral"


def _swedish_part(text: str) -> str:
    """Strip the English half from a Swedish+English paragraph."""
    if _lang(text) != "mixed":
        return "" if _lang(text) == "en" else text
    # The English duplicate follows the Swedish text after a "." (sometimes
    # glued on: "Räkor .Caesarsallad with ...") or, dot-less, after a "/".
    segments = [s for s in re.split(r"\s*\.\s*", text) if s.strip()]
    kept = [s for s in segments if _lang(s) != "en"]
    if kept and len(kept) < len(segments):
        return ". ".join(s.strip() for s in kept)
    # No usable dot split — try the "/ A Plate with ..." style.
    parts = [p for p in text.split("/") if p.strip()]
    kept = [p.strip() for p in parts if _lang(p) != "en"]
    if kept and len(kept) < len(parts):
        return "/ ".join(kept)
    return text


def _is_all_bold(p) -> bool:
    """True when the paragraph's entire visible text sits inside <strong>."""
    text = " ".join(p.get_text(" ", strip=True).split())
    if not text:
        return False
    strong = " ".join(
        " ".join(s.get_text(" ", strip=True).split()) for s in p.find_all("strong")
    ).strip()
    return strong == text


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")
    cards = soup.select("div.payload-richtext") or [soup]

    days: dict[str, list[Dish]] = {}
    for card in cards:
        day: str | None = None
        last_was_name = False
        for p in card.find_all("p"):
            text = " ".join(p.get_text(" ", strip=True).split())
            if not text or not text.strip(" .,-–"):
                last_was_name = False
                continue

            key = day_key(text)
            if key:
                day = key
                last_was_name = False
                continue
            # Skip the "Meny V.38" style card headings.
            if week_in_text(text) is not None and text.lower().startswith("meny"):
                last_was_name = False
                continue
            if day is None:
                continue

            if _lang(text) == "en":  # pure English duplicate
                last_was_name = False
                continue

            swedish = _swedish_part(text).strip(" .,")
            if not swedish:
                last_was_name = False
                continue

            dishes = days.setdefault(day, [])
            is_name = _is_all_bold(p) and _lang(text) in ("sv", "neutral")
            if is_name:
                dishes.append(Dish(swedish))
            elif last_was_name and dishes:
                # Description paragraph directly under its dish name.
                combined = f"{dishes[-1].text.rstrip(' .')} – {swedish}"
                dishes[-1] = Dish(combined)
            else:
                dishes.append(Dish(swedish))
            last_was_name = is_name

        # Drop accidental repeats (standing items appear once per day card).
        if day and day in days:
            seen: set[str] = set()
            days[day] = [
                d for d in days[day] if not (d.text in seen or seen.add(d.text))
            ]
    return {d: lst for d, lst in days.items() if lst}
