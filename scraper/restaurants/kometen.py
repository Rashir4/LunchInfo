"""Restaurang Kometen — Swedish husmanskost classic on Vasagatan (since 1934).

Kometen's own site (www.restaurangkometen.se, Wix) publishes the weekly lunch
under /menu, but the Wix edge range hosting that hostname is unreachable from
this network, so we scrape menydags.se's server-rendered mirror of the same
weekly menu instead. Each weekday card there repeats the fixed à-la-carte
sections; only the "Dagens - Lunch" section holds the changing daily dishes,
so that is all we keep.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="kometen",
    name="Restaurang Kometen",
    address="Vasagatan 58",
    url="https://www.restaurangkometen.se",
    menu_url="https://www.menydags.se/restaurang/kometen/lunch",
    walk_minutes=11,
    cuisine="Modern svenskt",
    price="159 kr",
    lunch_hours="11.30–14.30",
)

# Badge labels menydags puts on a dish -> our tag names.
_BADGE_TAGS = (
    ("vegetar", "veg"),
    ("vegan", "veg"),
    ("fisk", "fisk"),
    ("skaldjur", "fisk"),
)


def _badge_tag(li) -> str | None:
    """Map a menydags badge span ("Vegetariskt", "Fisk och skaldjur") to a tag."""
    for span in li.find_all("span"):
        label = span.get_text(" ", strip=True).lower()
        if len(label) > 30:
            continue
        for needle, tag in _BADGE_TAGS:
            if needle in label:
                return tag
    return None


def parse(html: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(html, "lxml")
    days: dict[str, list[Dish]] = {}

    # menydags renders one card per day: an <h3> "Måndag 14 september" heading
    # followed by <h4> menu sections. Walk headings in document order, keeping
    # only the "Dagens - Lunch" section of each weekday.
    current_day: str | None = None
    for heading in soup.find_all(["h3", "h4"]):
        text = heading.get_text(" ", strip=True)
        if heading.name == "h3":
            current_day = day_key(text)
            continue
        if current_day is None or not text.lower().startswith("dagens"):
            continue
        # Stop at the next section heading: find_next_sibling("ul") alone would
        # skip past it and publish the fixed à-la-carte list as today's lunch.
        ul = None
        for sibling in heading.find_next_siblings():
            if sibling.name in ("h2", "h3", "h4"):
                break
            if sibling.name == "ul":
                ul = sibling
                break
        if ul is None:
            continue
        dishes = days.setdefault(current_day, [])
        for li in ul.find_all("li"):
            # First <p> is the dish name, second its description; prices and
            # badges live in other elements and are deliberately left out.
            paragraphs = [p.get_text(" ", strip=True) for p in li.find_all("p")]
            paragraphs = [p for p in paragraphs if p]
            if not paragraphs:
                continue
            text_parts = paragraphs[:2]
            dish_text = " – ".join(text_parts) if len(text_parts) == 2 else text_parts[0]
            dish = Dish(dish_text, tag=_badge_tag(li))
            if dish.text:  # main.py dedupes across the whole day
                dishes.append(dish)

    return {day: dishes for day, dishes in days.items() if dishes}
