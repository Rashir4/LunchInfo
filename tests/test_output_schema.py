"""Validates site/data.json (when present) so a bad scrape can't ship."""

import json
from pathlib import Path

import pytest

from scraper.models import WEEKDAYS

DATA = Path(__file__).parent.parent / "site" / "data.json"

pytestmark = pytest.mark.skipif(not DATA.exists(), reason="data.json not generated yet")


@pytest.fixture(scope="module")
def payload():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_top_level_shape(payload):
    assert isinstance(payload["year"], int)
    assert 1 <= payload["week"] <= 53
    assert isinstance(payload["generated_at"], str)
    assert isinstance(payload["restaurants"], list)
    assert payload["restaurants"], "no restaurants in data.json"


def test_restaurant_entries(payload):
    seen_ids = set()
    for r in payload["restaurants"]:
        assert r["id"] not in seen_ids, f"duplicate id {r['id']}"
        seen_ids.add(r["id"])
        assert r["name"].strip()
        assert r["menu_url"].startswith("http")
        assert isinstance(r["walk_minutes"], int) and 1 <= r["walk_minutes"] <= 25
        assert set(r["days"]) <= set(WEEKDAYS)
        for day, dishes in r["days"].items():
            for dish in dishes:
                assert dish["text"].strip(), f"{r['id']}/{day}: empty dish"
                assert "<" not in dish["text"], f"{r['id']}/{day}: HTML in dish text"
                if "tag" in dish:
                    assert dish["tag"] in ("veg", "fisk")


def test_majority_scraped_ok(payload):
    ok = [r for r in payload["restaurants"] if not r.get("error")]
    assert len(ok) >= max(3, len(payload["restaurants"]) // 2), (
        "more than half of the restaurants failed to scrape: "
        + ", ".join(f"{r['id']} ({r['error']})" for r in payload["restaurants"] if r.get("error"))
    )


def test_ok_restaurants_have_dishes(payload):
    for r in payload["restaurants"]:
        if r.get("error"):
            continue
        total = sum(len(d) for d in r["days"].values())
        assert total > 0, f"{r['id']} has no error but zero dishes"


def test_filter_fields_present(payload):
    """The site's filters need cuisine on every restaurant and types on dishes."""
    for r in payload["restaurants"]:
        assert r.get("cuisine"), f"{r['id']}: no cuisine"
        for day, dishes in r["days"].items():
            for dish in dishes:
                for t in dish.get("types", []):
                    assert t in (
                        "veg", "fisk", "kott", "kyckling", "gryta", "pasta",
                        "soppa", "sallad", "sushi", "nudlar", "burgare",
                    ), f"{r['id']}/{day}: unknown food type {t!r}"


def test_badge_is_always_in_types(payload):
    """A veg/fisk badge must be filterable, or the two disagree on screen."""
    for r in payload["restaurants"]:
        for day, dishes in r["days"].items():
            for dish in dishes:
                if dish.get("tag"):
                    assert dish["tag"] in dish.get("types", []), (
                        f"{r['id']}/{day}: badge {dish['tag']} missing from types"
                    )
