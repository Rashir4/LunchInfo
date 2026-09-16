"""Heaven 23 — 23rd-floor restaurant in Gothia Towers, Mässans Gata 24.

The weekly lunch lives in a corner of the restaurant's full menu PDF, linked
from the lunch page under a filename that carries the week ("v38-Lunchmeny-
Heaven.pdf"); fetch() re-discovers that link each run and detect_week reads the
week off it. The same three dishes run Monday–Friday — the PDF says so in as
many words ("Serveras måndag - fredag fram till kl. 14.00") — so every weekday
gets the same list.

The PDF is a two-column bilingual menu, and pdfplumber's plain text extraction
interleaves the columns into nonsense. fetch() therefore rebuilds it: only the
left column, only the upright (Swedish) font — the English translations are set
in italic and would otherwise double every dish — with a blank line wherever the
vertical gap says a new entry starts. parse() then locates the lunch block among
those lines, so a menu that drops or renames the block fails loudly.
"""

from __future__ import annotations

import io
import re

from ..models import WEEKDAYS, Dish, Restaurant
from ..utils import week_in_text

RESTAURANT = Restaurant(
    id="heaven23",
    name="Heaven 23",
    address="Mässans Gata 24, 412 51 Göteborg",
    url="https://heaven23.se/",
    menu_url="https://heaven23.se/hem/restaurangen/lunch/",
    walk_minutes=7,
    cuisine="Modern svenskt",
    price="175 kr",
    lunch_hours="mån–fre 11.30–14.00",
)

_SOURCE_PREFIX = "source: "
_PDF_LINK_RE = re.compile(r'"(https://heaven23\.se/uploads/[^"]+\.pdf)"', re.IGNORECASE)

# Words starting at/after this x coordinate belong to the right-hand column.
_MAIN_COLUMN_MAX_X = 430
# Vertical tolerance (pt) when grouping words into one visual line.
_LINE_TOLERANCE = 4
# A vertical gap wider than this separates two menu entries rather than
# wrapping one; entry spacing is ~27pt, a wrapped line ~13pt.
_ENTRY_GAP = 20

_LUNCH_HEADING = re.compile(r"^veckans lunch\b", re.IGNORECASE)
# Price-only lines ("175", "195 / 275") and the serving-hours note carry no dish.
_PRICE_ONLY = re.compile(r"^\d{2,4}(?:\s*/\s*\d{2,4})*$")
_SERVING_NOTE = re.compile(r"^serveras\b", re.IGNORECASE)


def _swedish_lines(page) -> list[str]:
    """Left-column, non-italic lines of one page, blank-separated by entry."""
    words = [
        w for w in page.extract_words(extra_attrs=["fontname"])
        if w["x0"] < _MAIN_COLUMN_MAX_X and "italic" not in w["fontname"].casefold()
    ]
    words.sort(key=lambda w: (w["top"], w["x0"]))

    lines: list[tuple[float, str]] = []
    for word in words:
        if lines and word["top"] - lines[-1][0] <= _LINE_TOLERANCE:
            lines[-1] = (lines[-1][0], f"{lines[-1][1]} {word['text']}")
        else:
            lines.append((word["top"], word["text"]))

    out: list[str] = []
    previous: float | None = None
    for top, text in lines:
        if previous is not None and top - previous > _ENTRY_GAP:
            out.append("")
        out.append(text)
        previous = top
    return out


def fetch() -> str:
    """Find the current menu PDF and return its Swedish left column as text."""
    import pdfplumber

    from ..fetch import FetchError, fetch_bytes, fetch_html

    page_html = fetch_html(RESTAURANT.menu_url)
    links = [u for u in _PDF_LINK_RE.findall(page_html) if "lunch" in u.casefold()]
    if not links:
        raise FetchError("no lunch PDF link found on the Heaven 23 lunch page")
    url = links[0]

    lines = [f"{_SOURCE_PREFIX}{url}"]
    with pdfplumber.open(io.BytesIO(fetch_bytes(url))) as pdf:
        for page in pdf.pages:
            lines.append("")
            lines.extend(_swedish_lines(page))
    return "\n".join(lines)


def detect_week(raw: str) -> int | None:
    """The week the PDF names itself for, e.g. 'v38-Lunchmeny-Heaven.pdf'."""
    first = raw.split("\n", 1)[0]
    return week_in_text(first) if first.startswith(_SOURCE_PREFIX) else None


def _lunch_dishes(raw: str) -> list[Dish]:
    lines = raw.splitlines()[1:]  # line 0 is the source URL
    start = next(
        (i for i, line in enumerate(lines) if _LUNCH_HEADING.match(line.strip())),
        None,
    )
    if start is None:
        return []

    dishes: list[Dish] = []
    entry: list[str] = []
    for line in lines[start + 1:] + [""]:
        line = line.strip()
        if line:
            entry.append(line)
            continue
        if entry and not _PRICE_ONLY.match(entry[0]) and not _SERVING_NOTE.match(entry[0]):
            dishes.append(Dish(" – ".join(entry)))
        entry = []
    return dishes


def parse(raw: str) -> dict[str, list[Dish]]:
    dishes = _lunch_dishes(raw)
    if not dishes:
        return {}
    return {day: [Dish(d.text, tag=d.tag) for d in dishes] for day in WEEKDAYS}
