"""Village Citygate — Compass Group restaurant in the Citygate tower, Gårda.

The visible page is a JS SPA, but the full weekly menu is server-rendered in
the raw HTML twice:

* PRIMARY: <script type="application/ld+json" id="restaurant-structured-data">
  — schema.org Restaurant; hasMenu.hasMenuSection is one object per weekday
  with "validFrom" (ISO date) and "description" holding the day's dishes as a
  single string separated by non-breaking spaces. NOTE: an nbsp can also occur
  INSIDE a dish (CMS line-break artifact), so only nbsp preceded by whitespace
  is treated as a dish separator.
* FALLBACK: a <noscript> block with one <article> per day —
  <h3><time datetime="YYYY-MM-DD"> plus a <div> of dish <p>s delimited by
  <p>&nbsp;</p> spacers (consecutive non-spacer <p>s are one wrapped dish).

No prices on the page (weight-priced buffet, 32 kr/hg per kvartersmenyn).
"""

from __future__ import annotations

import datetime as dt
import html as htmllib
import json
import re

from bs4 import BeautifulSoup

from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import current_week

RESTAURANT = Restaurant(
    id="village-citygate",
    name="Village Citygate",
    address="Fabrikstorget 1, 412 50 Göteborg",
    url="https://www.compass-group.se/restauranger-och-menyer/ovriga-restauranger/village/",
    menu_url="https://www.compass-group.se/restauranger-och-menyer/ovriga-restauranger/village/",
    walk_minutes=22,
    cuisine="Varierat",
    price="32 kr/hg (viktpris, buffé)",
    lunch_hours="11.00–13.30",
)

# Dish separator in JSON-LD descriptions: an nbsp run that follows ordinary
# whitespace. The lookbehind excludes \xa0 explicitly — it is itself \s, so a
# run of two nbsp glued to a word would otherwise split one dish in half.
_SEP_RE = re.compile(r"(?<=[^\S\xa0])\xa0+")


def _weekday(date_str: str) -> str | None:
    """Day key for a section's validFrom date, or None if not this week.

    The feed sometimes carries more than one week; without the week check a
    later section would overwrite an earlier one and publish the wrong week.
    """
    try:
        date = dt.date.fromisoformat(date_str.strip()[:10])
    except ValueError:
        return None
    iso = date.isocalendar()
    if (iso.year, iso.week) != current_week():
        return None
    wd = date.weekday()
    return WEEKDAYS[wd] if wd < len(WEEKDAYS) else None  # skip Sat/Sun


def _parse_jsonld(soup: BeautifulSoup) -> dict[str, list[Dish]]:
    script = soup.find("script", id="restaurant-structured-data")
    if script is None or not script.string:
        return {}
    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return {}
    menu = data.get("hasMenu")
    sections = menu.get("hasMenuSection", []) if isinstance(menu, dict) else []

    days: dict[str, list[Dish]] = {}
    for section in sections:
        key = _weekday(str(section.get("validFrom", "")))
        if key is None:
            continue
        text = htmllib.unescape(section.get("description") or "")
        dishes = [Dish(part) for part in _SEP_RE.split(text) if part.strip()]
        if dishes:
            days[key] = dishes
    return days


def _parse_noscript(soup: BeautifulSoup) -> dict[str, list[Dish]]:
    days: dict[str, list[Dish]] = {}
    for noscript in soup.find_all("noscript"):
        # Some parsers expose <noscript> innerHTML as a text node — re-parse.
        inner = noscript.decode_contents()
        if "<article" not in inner:
            continue
        block = BeautifulSoup(inner, "lxml")
        for article in block.find_all("article"):
            time_el = article.find("time")
            if time_el is None or not time_el.get("datetime"):
                continue
            key = _weekday(time_el["datetime"])
            if key is None:
                continue
            div = article.find("div")
            if div is None:
                continue
            dishes: list[str] = []
            pending: list[str] = []
            for p in div.find_all("p"):
                text = p.get_text(" ", strip=True).replace("\xa0", " ").strip()
                if text:
                    pending.append(text)  # wrapped dish lines join up
                elif pending:
                    dishes.append(" ".join(pending))
                    pending = []
            if pending:
                dishes.append(" ".join(pending))
            if dishes:
                days[key] = [Dish(t) for t in dishes]
    return days


def parse(html: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(html, "lxml")
    return _parse_jsonld(soup) or _parse_noscript(soup)
