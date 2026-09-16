import pytest

from scraper.utils import current_week, day_key, is_day_heading, week_in_text


class TestDayKey:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Måndag", "mon"),
            ("MÅNDAG 8/9", "mon"),
            ("tisdag:", "tue"),
            ("Onsdag 10 september", "wed"),
            ("TORSDAG", "thu"),
            ("Fredag – dagens", "fri"),
            ("  Måndag  ", "mon"),
        ],
    )
    def test_weekdays(self, text, expected):
        assert day_key(text) == expected

    @pytest.mark.parametrize("text", ["Lördag", "Söndag", "Veckans sallad", "", None, "Månadens rätt"])
    def test_non_weekdays(self, text):
        assert day_key(text) is None


class TestIsDayHeading:
    def test_weekend_counts_as_heading(self):
        assert is_day_heading("Lördag brunch")

    def test_plain_text_does_not(self):
        assert not is_day_heading("Pannbiff med lök")


class TestWeekInText:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Lunchmeny Vecka 37", 37),
            ("v.37", 37),
            ("V 5", 5),
            ("vecka 53", 53),
            ("vecka 99", None),
            ("ingen vecka här", None),
            ("", None),
            (None, None),
        ],
    )
    def test_extraction(self, text, expected):
        assert week_in_text(text) == expected


def test_current_week_sane():
    year, week = current_week()
    assert 2026 <= year <= 2100
    assert 1 <= week <= 53
