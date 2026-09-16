"""Shared helpers for parsers: week numbers, Swedish day detection."""

from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

from .models import SWEDISH_DAYS, WEEKDAYS

# Matches a Swedish weekday at the start of a string, e.g. "Måndag", "MÅNDAG 8/9",
# "Tisdag:" — tolerant of case, trailing dates and punctuation.
_DAY_RE = re.compile(
    r"^\s*(måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag)\b",
    re.IGNORECASE,
)


def current_week() -> tuple[int, int]:
    """(ISO year, ISO week) for today in Gothenburg, regardless of host timezone."""
    today = dt.datetime.now(ZoneInfo("Europe/Stockholm")).date()
    iso = today.isocalendar()
    return iso.year, iso.week


def day_key(text: str) -> str | None:
    """Map a heading like 'MÅNDAG 8 september' to 'mon'; None for non-days.

    Saturday/Sunday match the regex but return None — we only track weekdays.
    """
    m = _DAY_RE.match(text or "")
    if not m:
        return None
    return SWEDISH_DAYS.get(m.group(1).lower())


def is_day_heading(text: str) -> bool:
    """True if the text starts with any Swedish day name (incl. weekend)."""
    return bool(_DAY_RE.match(text or ""))


def exact_day_key(text: str) -> str | None:
    """Map a line that is ONLY a weekday name ('Måndag', 'MÅNDAG:') to its key.

    Unlike day_key(), rejects lines with anything after the name ('Måndag 8/9'),
    so parsers can tell bare day headings apart from dish text mentioning a day.
    """
    stripped = (text or "").strip().rstrip(":").strip().lower()
    return SWEDISH_DAYS.get(stripped)


def day_key_for_date(date: dt.date) -> str | None:
    """'mon'..'fri' for a calendar date; None on weekends."""
    idx = date.weekday()
    return WEEKDAYS[idx] if idx < 5 else None


def week_in_text(text: str) -> int | None:
    """Extract a week number from text like 'Vecka 37' or 'v.37' or 'V 37'."""
    m = re.search(r"\b(?:vecka|v\.?)\s*(\d{1,2})\b", text or "", re.IGNORECASE)
    if m:
        week = int(m.group(1))
        if 1 <= week <= 53:
            return week
    return None
