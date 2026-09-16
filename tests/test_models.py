import pytest

from scraper.models import (
    Dish,
    Restaurant,
    ValidationError,
    classify_dish,
    clean_text,
)


class TestCleanText:
    def test_strips_tags_and_whitespace(self):
        assert clean_text("  <b>Köttbullar</b>\n med   mos ") == "Köttbullar med mos"

    def test_strips_nbsp_and_bullets(self):
        assert clean_text("•\xa0Pasta carbonara") == "Pasta carbonara"

    def test_keeps_swedish_chars(self):
        assert clean_text("Grönsakssoppa med örtcrème") == "Grönsakssoppa med örtcrème"

    def test_empty(self):
        assert clean_text("   ") == ""


class TestClassifyDish:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Stekt lax med dillsås", "fisk"),
            ("Vegetarisk lasagne", "veg"),
            ("Halloumiburgare med pommes", "veg"),
            ("Räksallad med rhode island", "fisk"),
            ("Köttbullar med potatismos", None),
            ("Kycklinggryta med ris", None),
        ],
    )
    def test_classification(self, text, expected):
        assert classify_dish(text) == expected


class TestDish:
    def test_auto_cleans_and_tags(self):
        d = Dish(" <i>Ugnsbakad torsk</i>  med ägg ")
        assert d.text == "Ugnsbakad torsk med ägg"
        assert d.tag == "fisk"

    def test_explicit_tag_wins(self):
        assert Dish("Dagens sopp", tag="veg").tag == "veg"

    @pytest.mark.parametrize("bad", ["", "ab", "x" * 301, "<div>oops</div>" + "<span>x</span>"])
    def test_validate_rejects_bad_text(self, bad):
        d = Dish("placeholder dish")
        d.text = bad  # bypass __post_init__ cleaning to test validate directly
        with pytest.raises(ValidationError):
            d.validate()


def make_restaurant(**overrides):
    kwargs = dict(
        id="test-place",
        name="Test Place",
        address="Testgatan 1",
        url="https://example.com",
        menu_url="https://example.com/lunch",
        walk_minutes=10,
    )
    kwargs.update(overrides)
    return Restaurant(**kwargs)


class TestRestaurant:
    def test_valid(self):
        r = make_restaurant(days={"mon": [Dish("Köttbullar med mos")]})
        r.validate()

    @pytest.mark.parametrize(
        "overrides",
        [
            {"id": "Bad Id!"},
            {"menu_url": "not-a-url"},
            {"walk_minutes": 0},
            {"walk_minutes": 60},
            {"days": {"saturday": []}},
        ],
    )
    def test_invalid(self, overrides):
        with pytest.raises(ValidationError):
            make_restaurant(**overrides).validate()

    def test_bad_dish_reports_restaurant_and_day(self):
        r = make_restaurant(days={"mon": [Dish("valid dish here")]})
        r.days["mon"][0].text = ""
        with pytest.raises(ValidationError, match="test-place/mon"):
            r.validate()

    def test_to_json_shape(self):
        r = make_restaurant(days={"fri": [Dish("Stekt strömming")]})
        j = r.to_json()
        assert j["id"] == "test-place"
        assert j["days"]["fri"][0] == {
            "text": "Stekt strömming", "tag": "fisk", "types": ["fisk"],
        }
        assert j["error"] is None
