"""Parser tests, auto-parametrized over every registered restaurant.

Each restaurant module gets:
  - a static-facts sanity check (always runs)
  - a fixture-based parse test (runs when tests/fixtures/<id>.html exists;
    fixtures are saved with `python -m scraper.main --save-fixtures`)
"""

from pathlib import Path

import pytest

from scraper import restaurants
from scraper.models import WEEKDAYS, Dish, Restaurant

FIXTURES = Path(__file__).parent / "fixtures"

MODULES = restaurants.all_modules()


def module_id(module):
    return module.RESTAURANT.id


@pytest.mark.parametrize("module", MODULES, ids=module_id)
class TestStaticFacts:
    def test_restaurant_declared(self, module):
        assert isinstance(module.RESTAURANT, Restaurant)
        r = module.RESTAURANT
        # validate() without menu data checks id/urls/walk_minutes
        r.validate()
        assert r.url.startswith("http")
        assert callable(module.parse)

    def test_id_matches_module_name(self, module):
        assert module.RESTAURANT.id.replace("-", "_") == module.__name__.rsplit(".", 1)[-1]


def fixture_modules():
    return [m for m in MODULES if (FIXTURES / f"{m.RESTAURANT.id}.html").exists()]


@pytest.mark.parametrize("module", fixture_modules(), ids=module_id)
class TestParseFixture:
    @pytest.fixture()
    def days(self, module):
        raw = (FIXTURES / f"{module.RESTAURANT.id}.html").read_text(encoding="utf-8")
        return module.parse(raw)

    def test_returns_weekday_menus(self, module, days):
        assert isinstance(days, dict)
        assert set(days) <= set(WEEKDAYS), f"unexpected day keys: {set(days) - set(WEEKDAYS)}"
        non_empty = [d for d in days.values() if d]
        assert non_empty, "parser found no dishes in fixture"
        # A weekly lunch place should publish at least 3 weekdays.
        assert len(non_empty) >= 3, f"only {len(non_empty)} days with dishes"

    def test_dishes_are_valid(self, module, days):
        for day, dishes in days.items():
            for dish in dishes:
                assert isinstance(dish, Dish)
                dish.validate()

    def test_no_day_headings_leaked_into_dishes(self, module, days):
        from scraper.utils import is_day_heading

        for dishes in days.values():
            for dish in dishes:
                assert not is_day_heading(dish.text), f"day heading leaked: {dish.text!r}"

    def test_reasonable_dish_counts(self, module, days):
        for day, dishes in days.items():
            assert len(dishes) <= 15, f"{day}: {len(dishes)} dishes — parser likely over-matching"

    def test_no_duplicate_dishes_within_day(self, module, days):
        for day, dishes in days.items():
            texts = [d.text for d in dishes]
            assert len(texts) == len(set(texts)), f"{day}: duplicate dishes {texts}"


def test_full_scrape_validates_against_registry():
    """Every module id is unique across the registry."""
    ids = [m.RESTAURANT.id for m in MODULES]
    assert len(ids) == len(set(ids)), "duplicate restaurant ids"
