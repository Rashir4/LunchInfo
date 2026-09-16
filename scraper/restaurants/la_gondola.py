"""La Gondola Trattoria — Kungsportsavenyn 4.

The weekly lunch menu ("Dagens lunch v.NN") is a PDF linked from the
single-page site at gondola.se; the link's filename changes every week
(e.g. Lunch-v.37.pdf), so fetch() re-discovers it from the homepage.

The PDF has two columns: the weekly Mon–Fri menu on the left and a fixed
"ALLTID PÅ MENYN" sidebar on the right. fetch() keeps only left-column
words (x0 < 385pt) and rebuilds line-per-line text, which parse() consumes.
"""

from __future__ import annotations

import html as htmllib
import io
import re

from ..models import Dish, Restaurant
from ..utils import day_key

RESTAURANT = Restaurant(
    id="la-gondola",
    name="La Gondola",
    address="Kungsportsavenyn 4",
    url="https://gondola.se/",
    menu_url="https://gondola.se/",
    walk_minutes=13,
    cuisine="Italienskt",
    price="139 kr",
    lunch_hours="11.30–14.30",
)

# Words starting at/after this x coordinate belong to the fixed sidebar.
_MAIN_COLUMN_MAX_X = 385
# Vertical tolerance (pt) when grouping words into visual lines.
_LINE_TOLERANCE = 3

_PDF_LINK_RE = re.compile(r'href="([^"]+/Lunch[^"]*\.pdf[^"]*)"', re.IGNORECASE)
# A new dish starts with a protein/diet label, e.g. "Kött:", "Fisk:", "Veg:".
_DISH_START_RE = re.compile(r"^(kött|fisk|veg\w*|vegan\w*)\s*:", re.IGNORECASE)


def fetch() -> str:
    """Find this week's lunch PDF on the homepage and extract its menu text."""
    import pdfplumber

    from ..fetch import FetchError, fetch_bytes, fetch_html

    page_html = fetch_html(RESTAURANT.menu_url)
    m = _PDF_LINK_RE.search(page_html)
    if not m:
        raise FetchError("no lunch PDF link found on gondola.se")
    pdf_url = htmllib.unescape(m.group(1))

    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(fetch_bytes(pdf_url))) as pdf:
        for page in pdf.pages:
            words = [w for w in page.extract_words() if w["x0"] < _MAIN_COLUMN_MAX_X]
            words.sort(key=lambda w: w["top"])
            row: list[dict] = []
            for word in words:
                if row and word["top"] - row[0]["top"] > _LINE_TOLERANCE:
                    row.sort(key=lambda w: w["x0"])
                    lines.append(" ".join(w["text"] for w in row))
                    row = []
                row.append(word)
            if row:
                row.sort(key=lambda w: w["x0"])
                lines.append(" ".join(w["text"] for w in row))
    return "\n".join(lines)


def parse(raw: str) -> dict[str, list[Dish]]:
    """Parse the left-column PDF text: day headings, then Kött:/Fisk: dishes."""
    days: dict[str, list[Dish]] = {}
    current_day: str | None = None
    current_dish: list[str] = []

    def flush() -> None:
        nonlocal current_dish
        if current_day and current_dish:
            days.setdefault(current_day, []).append(Dish(" ".join(current_dish)))
        current_dish = []

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        key = day_key(line)
        if key:
            flush()
            current_day = key
            continue
        if current_day is None:
            continue  # header block (price, week number) before Monday
        if _DISH_START_RE.match(line) or not current_dish:
            flush()
            current_dish = [line]
        else:
            current_dish.append(line)  # wrapped continuation of the dish
    flush()
    return days
