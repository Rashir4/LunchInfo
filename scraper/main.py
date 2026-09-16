"""Orchestrator: run every restaurant scraper and emit site/data.json.

Usage:
  python -m scraper.main                 # scrape everything, write site/data.json
  python -m scraper.main --only wijkanders,toso
  python -m scraper.main --save-fixtures # also save raw pages to tests/fixtures/
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

from . import restaurants
from .fetch import fetch_html
from .models import Restaurant, ValidationError
from .utils import current_week

ROOT = Path(__file__).resolve().parent.parent
SITE_DATA = ROOT / "site" / "data.json"
FIXTURES = ROOT / "tests" / "fixtures"

# The build fails outright unless this many restaurants scrape cleanly — a
# mostly-empty site is worse than a stale one. Mirrors the output contract in
# tests/test_output_schema.py::test_majority_scraped_ok, so a run that would
# produce data the test suite rejects never gets written.
MIN_SUCCESSFUL = 3


def _required_successes(total: int) -> int:
    return max(MIN_SUCCESSFUL, total // 2)


def _dedupe_days(days: dict[str, list]) -> dict[str, list]:
    """Drop repeated dish texts within a day, preserving order.

    Sites routinely list a dish twice (desktop + mobile blocks, a weekly
    special repeated under its own heading). Doing it here means parsers do
    not each need their own dedup pass.
    """
    out = {}
    for day, dishes in days.items():
        position: dict[str, int] = {}
        unique: list = []
        for dish in dishes:
            index = position.get(dish.text)
            if index is None:
                position[dish.text] = len(unique)
                unique.append(dish)
            elif unique[index].tag is None and dish.tag is not None:
                # Keep the copy that carries a badge: the same dish often
                # appears once plain and once under a "Veckans vegetariska"
                # heading, and the tagged one is the informative version.
                unique[index] = dish
        out[day] = unique
    return out


def scrape_one(module: ModuleType, save_fixtures: bool = False) -> Restaurant:
    """Fetch + parse one restaurant; failures are recorded, never raised."""
    # Never mutate the module-level Restaurant: repeated runs (or tests
    # sharing the process) must each start from clean static facts.
    rest = copy.deepcopy(module.RESTAURANT)
    try:
        if hasattr(module, "fetch"):
            raw = module.fetch()
        else:
            raw = fetch_html(rest.menu_url)
        if save_fixtures:
            FIXTURES.mkdir(parents=True, exist_ok=True)
            (FIXTURES / f"{rest.id}.html").write_text(raw, encoding="utf-8")
        rest.days = _dedupe_days(module.parse(raw))
        if not any(rest.days.values()):
            raise ValidationError("parser returned no dishes for any weekday")
        # A page that labels its own week lets us catch a restaurant that has
        # not published the new week yet, rather than showing last week's food
        # under this week's heading.
        if hasattr(module, "detect_week"):
            claimed = module.detect_week(raw)
            if claimed is not None and claimed != current_week()[1]:
                rest.stale_week = claimed
        rest.validate()
    except Exception as exc:  # noqa: BLE001 — every failure is recorded per restaurant
        rest.days = {}
        rest.error = f"{type(exc).__name__}: {exc}"
    return rest


def scrape_all(only: set[str] | None = None, save_fixtures: bool = False) -> list[Restaurant]:
    modules = restaurants.all_modules()
    if only:
        modules = [m for m in modules if m.RESTAURANT.id in only]
        missing = only - {m.RESTAURANT.id for m in modules}
        if missing:
            sys.exit(f"unknown restaurant ids: {', '.join(sorted(missing))}")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda m: scrape_one(m, save_fixtures), modules))
    return sorted(results, key=lambda r: (r.walk_minutes, r.name.lower()))


def build_payload(results: list[Restaurant]) -> dict:
    year, week = current_week()
    return {
        "year": year,
        "week": week,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "anchor": "Lennart Torstenssonsgatan, Göteborg",
        "restaurants": [r.to_json() for r in results],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated restaurant ids")
    ap.add_argument("--save-fixtures", action="store_true",
                    help="save fetched pages to tests/fixtures/")
    ap.add_argument("--dry-run", action="store_true",
                    help="print summary, do not write data.json")
    args = ap.parse_args()

    only = set(args.only.split(",")) if args.only else None
    results = scrape_all(only, args.save_fixtures)

    ok = [r for r in results if not r.error]
    failed = [r for r in results if r.error]
    for r in ok:
        days = sum(1 for d in r.days.values() if d)
        dishes = sum(len(d) for d in r.days.values())
        print(f"  OK   {r.id}: {dishes} dishes over {days} days")
    for r in failed:
        print(f"  FAIL {r.id}: {r.error}", file=sys.stderr)

    if not only:
        required = _required_successes(len(results))
        if len(ok) < required:
            sys.exit(
                f"only {len(ok)}/{len(results)} restaurants scraped cleanly "
                f"(need {required}); refusing to write data.json"
            )

    if args.dry_run:
        return

    # --only runs merge into existing data instead of clobbering the full set —
    # but never across week boundaries, or stale menus would wear the new week's label.
    payload = build_payload(results)
    if only and SITE_DATA.exists():
        existing = json.loads(SITE_DATA.read_text(encoding="utf-8"))
        if (existing.get("year"), existing.get("week")) != (payload["year"], payload["week"]):
            sys.exit(
                f"data.json is from week {existing.get('week')}/{existing.get('year')}; "
                "run a full scrape instead of --only to start the new week"
            )
        merged = {r["id"]: r for r in existing.get("restaurants", [])}
        for r in payload["restaurants"]:
            merged[r["id"]] = r
        payload["restaurants"] = sorted(
            merged.values(), key=lambda r: (r["walk_minutes"], r["name"].lower())
        )

    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"wrote {SITE_DATA} — week {payload['week']}, "
          f"{len(ok)}/{len(results)} restaurants ok")


if __name__ == "__main__":
    main()
