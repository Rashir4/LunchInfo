"""Shared client for the Plate Impact menu API (Chalmers-area restaurants).

Several campus restaurants publish their weekly menu through an Angular SPA at
plateimpact-screen.azurewebsites.net, backed by a GraphQL API. The page itself
renders client-side, so parsers fetch the API directly.

The leading underscore keeps this module out of the auto-discovering registry
in ``restaurants/__init__.py``.
"""

from __future__ import annotations

import datetime as dt
import json

from ..fetch import FetchError, post_json
from ..utils import current_week, day_key_for_date

GRAPHQL_URL = "https://plateimpact-heimdall.azurewebsites.net/graphql"

QUERY = """\
query DishOccurrences($unit: String!, $start: String!, $end: String!) {
  dishOccurrencesByTimeRange(mealProvidingUnitID: $unit, startDate: $start, endDate: $end) {
    startDate
    dishType { name }
    dish { name }
    displayNames { name categoryName sortOrder }
  }
}
"""

# The API labels the Swedish display name differently per unit — "Swedish" for
# some, "Svenska" for others — so accept both spellings.
_SWEDISH_CATEGORIES = ("swed", "svensk")

# Observed startDate spellings; the API has used all three across units.
_DATE_FORMATS = ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d")


def fetch_week(unit_id: str) -> str:
    """POST the SPA's query for the current ISO week (Mon–Fri); return raw JSON.

    The API rejects GET (Apollo CSRF guard), so this goes through the shared
    POST helper, inheriting its UA, timeout, retries and size cap.
    """
    year, week = current_week()
    monday = dt.date.fromisocalendar(year, week, 1)
    friday = monday + dt.timedelta(days=4)
    return post_json(
        GRAPHQL_URL,
        {
            "query": QUERY,
            "variables": {
                "unit": unit_id,
                "start": monday.isoformat(),
                "end": friday.isoformat(),
            },
        },
    )


def _occurrence_date(raw: str) -> dt.date | None:
    raw = (raw or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _dish_name(occurrence: dict) -> str:
    """Swedish display name, falling back to any display name, then dish name."""
    names = sorted(
        occurrence.get("displayNames") or [], key=lambda n: n.get("sortOrder") or 0
    )
    for entry in names:
        category = (entry.get("categoryName") or "").lower()
        if category.startswith(_SWEDISH_CATEGORIES) and entry.get("name"):
            return entry["name"]
    for entry in names:
        if entry.get("name"):
            return entry["name"]
    return (occurrence.get("dish") or {}).get("name") or ""


def iter_occurrences(raw: str):
    """Yield (day_key, station, dish_name) for each weekday occurrence.

    Raises FetchError if no date in the payload could be parsed at all, so a
    format drift surfaces as a scrape failure instead of a silently empty menu.
    """
    payload = json.loads(raw)
    occurrences = (payload.get("data") or {}).get("dishOccurrencesByTimeRange") or []

    rows = []
    undated = 0
    for occ in occurrences:
        name = _dish_name(occ)
        if not name.strip():
            continue
        date = _occurrence_date(occ.get("startDate", ""))
        if date is None:
            undated += 1
            continue
        day = day_key_for_date(date)
        if day is None:  # weekend
            continue
        station = ((occ.get("dishType") or {}).get("name") or "").strip()
        rows.append((day, station, name))

    # Raise when unparseable dates are not a clear minority: a partial drift
    # would otherwise publish a near-empty week with no error at all.
    if undated and undated >= len(rows):
        raise FetchError(
            f"{undated} of {undated + len(rows)} occurrences had an unreadable "
            "startDate — Plate Impact date format may have changed"
        )
    return rows
