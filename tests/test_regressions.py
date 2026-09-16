"""Regression tests: each case is a bug found in review and fixed.

Named by the failure they prevent, so a reintroduction says what broke.
"""

from __future__ import annotations

import datetime as dt
import re
from unittest import mock

import pytest
import requests
from bs4 import BeautifulSoup

from scraper import fetch as fetch_mod
from scraper.main import _dedupe_days, _required_successes
from scraper.models import Dish, classify_dish
from scraper.restaurants import _plateimpact
from scraper.utils import current_week, day_key_for_date, exact_day_key


class TestDishClassification:
    """Meat dishes used to be badged 'veg' because of side-dish keywords."""

    @pytest.mark.parametrize(
        "text",
        [
            "Fläskfilé med säsongens grönt",
            "Kycklingspett med halloumi och tzatziki",
            "Pannbiff med lök och gräddsås",
            "Kalvschnitzel med grönsaker",
        ],
    )
    def test_meat_dish_is_never_tagged_veg(self, text):
        assert classify_dish(text) != "veg"

    @pytest.mark.parametrize(
        "text",
        ["Vegetarisk lasagne", "Halloumiburgare", "Falafel med hummus", "Vegansk gryta"],
    )
    def test_vegetarian_dishes_still_tagged(self, text):
        assert classify_dish(text) == "veg"

    @pytest.mark.parametrize(
        "text",
        ["Stekt strömming", "Räksallad", "Ugnsbakad lax", "Fiskgratäng", "Kokt torsk"],
    )
    def test_fish_dishes_tagged(self, text):
        assert classify_dish(text) == "fisk"

    @pytest.mark.parametrize(
        "text",
        [
            "Serveras med rostad potatis",   # 'sej' hides inside 'serveras'
            "Pasta carbonara",
            "Kycklinggryta med ris",
        ],
    )
    def test_no_spurious_tag_from_substring(self, text):
        assert classify_dish(text) is None

    def test_explicit_veg_label_beats_any_protein_word(self):
        """The kitchen's own label is authoritative: "Vegetarisk schnitzel"
        is vegetarian, and mislabelling it lost the badge on live data."""
        for text in [
            "Vegetarisk schnitzel, örtkräm, gröna ärtor",
            "VEG: Vegetariska biffar, kokt potatis",
            "Vegansk pannbiff med lök",
            "Vegetarisk korv med potatismos",
        ]:
            assert classify_dish(text) == "veg", text

    def test_earliest_named_protein_wins_over_garnish(self):
        """A later protein is garnish — this mis-tagged pork as fish live."""
        assert classify_dish(
            "Fläskschnitzel med rödvinssås, krossad potatis med ansjovis"
        ) is None
        assert classify_dish(
            "Caesarsallad med Kyckling och Bacon eller med Räkor"
        ) is None
        assert classify_dish("Lax med bacongratinerad potatis") == "fisk"

    def test_meatfree_protein_beats_later_meat_word(self):
        assert classify_dish("Quorn-biff med rotfrukter") == "veg"
        assert classify_dish("Halloumisallad med rostade nötter") == "veg"

    def test_nut_is_not_beef(self):
        """'nöt' as a bare keyword matched 'nötter' (nuts)."""
        assert classify_dish("Sallad med rostade nötter och fetaost") != "fisk"
        assert classify_dish("Grönsallad med valnötter") is None


class TestFetchRetryPolicy:
    """5xx used to skip the retry loop while 4xx burned all three attempts."""

    def _response(self, status):
        resp = mock.Mock(spec=requests.Response)
        resp.status_code = status
        resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        resp.iter_content = lambda chunk_size=0: [b"<html>ok</html>"]
        resp.close = lambda: None
        resp.text = "<html>ok</html>"
        return resp

    def test_transient_5xx_is_retried_then_succeeds(self):
        responses = [self._response(503), self._response(200)]
        with mock.patch.object(fetch_mod._session, "request",
                               side_effect=responses) as req, \
             mock.patch.object(fetch_mod.time, "sleep"):
            fetch_mod.fetch_html("https://example.test/lunch")
        assert req.call_count == 2

    def test_permanent_4xx_fails_immediately(self):
        with mock.patch.object(fetch_mod._session, "request",
                               return_value=self._response(404)) as req, \
             mock.patch.object(fetch_mod.time, "sleep"):
            with pytest.raises(fetch_mod.FetchError, match="404"):
                fetch_mod.fetch_html("https://example.test/gone")
        assert req.call_count == 1

    def test_persistent_5xx_gives_up_after_retries(self):
        with mock.patch.object(fetch_mod._session, "request",
                               return_value=self._response(500)) as req, \
             mock.patch.object(fetch_mod.time, "sleep"):
            with pytest.raises(fetch_mod.FetchError):
                fetch_mod.fetch_html("https://example.test/down")
        assert req.call_count == fetch_mod.RETRIES

    def test_explicit_charset_header_is_trusted(self):
        resp = self._response(200)
        resp.headers = {"Content-Type": "text/html; charset=iso-8859-1"}
        resp.encoding = "ISO-8859-1"
        resp.apparent_encoding = "MacRoman"
        with mock.patch.object(fetch_mod._session, "request", return_value=resp):
            fetch_mod.fetch_html("https://example.test/latin1")
        assert resp.encoding == "ISO-8859-1"  # not overwritten by the sniffer


class TestWeekHandling:
    def test_current_week_uses_stockholm_time(self):
        """A UTC host late on Sunday is already in next ISO week in Sweden."""
        year, week = current_week()
        stockholm = dt.datetime.now(dt.timezone.utc).astimezone(
            __import__("zoneinfo").ZoneInfo("Europe/Stockholm")
        ).date().isocalendar()
        assert (year, week) == (stockholm.year, stockholm.week)

    def test_day_key_for_date_skips_weekend(self):
        monday = dt.date.fromisocalendar(2026, 38, 1)
        assert day_key_for_date(monday) == "mon"
        assert day_key_for_date(monday + dt.timedelta(days=4)) == "fri"
        assert day_key_for_date(monday + dt.timedelta(days=5)) is None

    @pytest.mark.parametrize(
        "text,expected",
        [("Måndag", "mon"), ("FREDAG:", "fri"), (" tisdag ", "tue"),
         ("Måndag 8/9", None), ("Veckans sallad", None), ("Lördag", None)],
    )
    def test_exact_day_key_rejects_decorated_headings(self, text, expected):
        assert exact_day_key(text) == expected


class TestOutputGates:
    def test_required_successes_follows_majority_rule(self):
        # Matches tests/test_output_schema.py::test_majority_scraped_ok.
        assert _required_successes(31) == 15
        assert _required_successes(4) == 3   # floor of 3 for small sets
        assert _required_successes(2) == 3   # never below the floor

    def test_dedupe_days_preserves_order_and_drops_repeats(self):
        days = {"mon": [Dish("Köttbullar med mos"), Dish("Stekt lax"),
                        Dish("Köttbullar med mos")]}
        out = _dedupe_days(days)
        assert [d.text for d in out["mon"]] == ["Köttbullar med mos", "Stekt lax"]


class TestPlateImpactClient:
    """The three campus parsers used to each carry a divergent copy."""

    def _payload(self, category, date_str):
        return (
            '{"data":{"dishOccurrencesByTimeRange":[{"startDate":"%s",'
            '"dishType":{"name":"Nordic"},"dish":{"name":"internal"},'
            '"displayNames":[{"name":"Köttbullar","categoryName":"%s","sortOrder":1}]}]}}'
            % (date_str, category)
        )

    @pytest.mark.parametrize("category", ["Swedish", "Svenska"])
    def test_both_swedish_category_spellings(self, category):
        """The API labels units differently; a single spelling broke one set."""
        rows = _plateimpact.iter_occurrences(
            self._payload(category, "09/14/2026 00:00:00")
        )
        assert [r[2] for r in rows] == ["Köttbullar"]

    @pytest.mark.parametrize(
        "date_str", ["09/14/2026 00:00:00", "09/14/2026", "2026-09-14"]
    )
    def test_accepts_every_observed_date_format(self, date_str):
        rows = _plateimpact.iter_occurrences(self._payload("Swedish", date_str))
        assert rows and rows[0][0] == "mon"

    def test_unparseable_dates_raise_instead_of_silent_empty(self):
        with pytest.raises(fetch_mod.FetchError, match="date format"):
            _plateimpact.iter_occurrences(
                self._payload("Swedish", "14.09.2026 kl 12")
            )


class TestParserStructuralBugs:
    def test_at_park_splits_dishes_on_double_br(self):
        from scraper.restaurants.at_park import _split_on_double_br

        soup = BeautifulSoup(
            "<p>Köttbullar med gräddsås<br><br>Stekt fisk med remoulad</p>", "lxml"
        )
        assert _split_on_double_br(soup.p) == [
            "Köttbullar med gräddsås",
            "Stekt fisk med remoulad",
        ]

    def test_at_park_single_br_keeps_one_dish(self):
        from scraper.restaurants.at_park import _split_on_double_br

        soup = BeautifulSoup("<p>Ugnsbakad torsk<br>med citronsås</p>", "lxml")
        assert _split_on_double_br(soup.p) == ["Ugnsbakad torsk med citronsås"]

    def test_aptitgarden_missing_day_does_not_steal_next_day(self):
        """A day with a heading but no text widget must stay empty."""
        from scraper.restaurants import aptitgarden

        html = """<div id="vecko-meny">
          <div class="elementor-widget-heading">
            <h2 class="elementor-heading-title">Tisdag</h2></div>
          <div class="elementor-widget-heading">
            <h2 class="elementor-heading-title">Onsdag</h2></div>
          <div class="elementor-widget-text-editor">
            <p>Onsdagsrätt med potatis</p></div>
        </div>"""
        days = aptitgarden.parse(html)
        assert "tue" not in days
        assert [d.text for d in days["wed"]] == ["Onsdagsrätt med potatis"]

    def test_kometen_skips_to_next_section_not_past_it(self):
        """An empty Dagens section must not borrow the à-la-carte list."""
        from scraper.restaurants import kometen

        html = """
        <h3>Måndag</h3>
        <h4>Dagens - Lunch</h4>
        <h4>Klassiker</h4>
        <ul><li><p>Fast à la carte-rätt</p></li></ul>
        """
        assert kometen.parse(html) == {}

    def test_sofina_keeps_rows_with_escaped_apostrophes(self):
        from scraper.restaurants import sofina

        year, week = current_week()
        monday = dt.date.fromisocalendar(year, week, 1).strftime("%d-%m-%Y")
        raw = (
            "var items = [['%s', 'Coq au vin \\'orange', 'Serveras med puré', 129],"
            "['%s', 'Nästa rätt', 'Beskrivning', 129]];" % (monday, monday)
        )
        texts = [d.text for d in sofina.parse(raw)["mon"]]
        assert any("orange" in t for t in texts)
        assert any("Nästa rätt" in t for t in texts)

    def test_village_citygate_keeps_glued_nbsp_dish_intact(self):
        from scraper.restaurants.village_citygate import _SEP_RE

        assert _SEP_RE.split("Pannbiff med lök och\xa0\xa0potatismos") == [
            "Pannbiff med lök och\xa0\xa0potatismos"
        ]
        assert _SEP_RE.split("Rätt ett \xa0Rätt två") == ["Rätt ett ", "Rätt två"]

    def test_hotell_heden_keeps_dish_mentioning_boilerplate_word(self):
        from scraper.restaurants.hotell_heden import _BOILERPLATE_PREFIXES

        dish = "Fläskfilé med potatisgratäng, inkl. sallad och bröd"
        assert not dish.lower().startswith(_BOILERPLATE_PREFIXES)
        assert "inkl. kaffe och kaka".startswith(_BOILERPLATE_PREFIXES)

    def test_ullevi_extends_repeated_weekday_block(self):
        """Two <p> blocks for one day must combine, not overwrite."""
        from scraper.restaurants import ullevi_restaurang_konferens as ullevi

        html = """<div class="text white">
          <p>Måndag<br>Första rätten med potatis</p>
          <p>Måndag<br>Andra rätten med ris</p>
        </div>"""
        texts = [d.text for d in ullevi.parse(html)["mon"]]
        assert texts == ["Första rätten med potatis", "Andra rätten med ris"]


class TestSurrLunchDayHeadings:
    def test_day_heading_with_date_is_recognised(self):
        """'Onsdag 17/9' used to be treated as a dish under Tuesday."""
        from scraper.restaurants import surr_lunch

        html = """<div class="day"><div class="meny">
          Tisdag<br>Kött<br>Tisdagsrätt med potatis 125 kr<br>
          Onsdag 17/9<br>Kött<br>Onsdagsrätt med ris 125 kr<br>
        </div></div>"""
        days = surr_lunch.parse(html)
        assert [d.text for d in days["tue"]] == ["Tisdagsrätt med potatis 125 kr"]
        assert [d.text for d in days["wed"]] == ["Onsdagsrätt med ris 125 kr"]


class TestStaleWeekDetection:
    """A restaurant that has not published the new week used to show last
    week's food under the current week's heading with no indication."""

    def test_le_comptoir_reports_the_week_its_page_claims(self):
        from scraper.restaurants import le_comptoir

        raw = 'some wix json {"sig":"v19-41"} ... <span>Lunchmeny v37</span>'
        assert le_comptoir.detect_week(raw) == 37

    def test_internal_ids_are_not_mistaken_for_a_week(self):
        """The raw Wix payload is full of ids like 'v19-41'."""
        from scraper.restaurants import le_comptoir

        assert le_comptoir.detect_week('{"sig":"v19-41","x":"style-lg5eryv65"}') is None

    def test_out_of_range_week_rejected(self):
        from scraper.restaurants import le_comptoir

        assert le_comptoir.detect_week("Lunchmeny v99") is None

    def test_scrape_one_flags_a_stale_week(self):
        from types import SimpleNamespace

        from scraper.main import scrape_one
        from scraper.models import Restaurant

        current = current_week()[1]
        module = SimpleNamespace(
            RESTAURANT=Restaurant(
                id="stale-test", name="Stale", address="", url="https://e.test",
                menu_url="https://e.test/lunch", walk_minutes=5,
            ),
            fetch=lambda: "raw",
            parse=lambda raw: {"mon": [Dish("Dagens rätt med potatis")]},
            detect_week=lambda raw: current - 1,
        )
        result = scrape_one(module)
        assert result.error is None
        assert result.stale_week == current - 1

    def test_current_week_is_not_flagged(self):
        from types import SimpleNamespace

        from scraper.main import scrape_one
        from scraper.models import Restaurant

        module = SimpleNamespace(
            RESTAURANT=Restaurant(
                id="fresh-test", name="Fresh", address="", url="https://e.test",
                menu_url="https://e.test/lunch", walk_minutes=5,
            ),
            fetch=lambda: "raw",
            parse=lambda raw: {"mon": [Dish("Dagens rätt med potatis")]},
            detect_week=lambda raw: current_week()[1],
        )
        assert scrape_one(module).stale_week is None


class TestDedupeKeepsTag:
    def test_tagged_duplicate_wins_over_untagged(self):
        """A weekly veg dish repeated as a plain day dish kept losing its badge."""
        days = {"mon": [Dish("Rotfruktsgratäng med sallad", tag=None),
                        Dish("Fläskfilé med potatis"),
                        Dish("Rotfruktsgratäng med sallad", tag="veg")]}
        out = _dedupe_days(days)
        assert [(d.text, d.tag) for d in out["mon"]] == [
            ("Rotfruktsgratäng med sallad", "veg"),
            ("Fläskfilé med potatis", None),
        ]


class TestKvartersmenynDecoys:
    def test_mid_word_decoy_does_not_split_a_dish(self):
        """kvartersmenyn injects hidden <i> junk; removing it used to leave a
        line break in the middle of the dish name."""
        from scraper.restaurants import _kvartersmenyn

        html = (
            '<div class="day"><div class="meny">Tisdag<br>Kött<br>'
            'Pann<i style="opacity:0.1">xq</i>biff med lök och gräddsås 125 kr'
            "</div></div>"
        )
        assert _kvartersmenyn.menu_lines(html) == [
            "Tisdag", "Kött", "Pannbiff med lök och gräddsås 125 kr",
        ]

    @pytest.mark.parametrize("module_name", ["gaffelkonst", "bombay_street", "surr_lunch"])
    def test_dated_day_headings_recognised(self, module_name):
        """'Onsdag 17/9' used to become a dish filed under the previous day."""
        import importlib

        module = importlib.import_module(f"scraper.restaurants.{module_name}")
        # The title satisfies gaffelkonst's wrong-restaurant guard.
        html = (
            "<html><head><title>Gaffelkonst</title></head><body>"
            '<div class="day"><div class="meny">'
            "Tisdag<br>Tisdagsrätt med potatis<br>"
            "Onsdag 17/9<br>Onsdagsrätt med ris"
            "</div></div></body></html>"
        )
        days = module.parse(html)
        joined = " ".join(d.text for d in days.get("tue", []))
        assert "Onsdag" not in joined, f"{module_name} leaked a heading into Tuesday"
        assert days.get("wed"), f"{module_name} lost Wednesday"


class TestPlateImpactPartialDrift:
    def test_partial_date_drift_raises_instead_of_shipping_one_day(self):
        """A drift affecting most days used to publish a near-empty week."""
        good = ('{"startDate":"09/14/2026 00:00:00","dishType":{"name":"N"},'
                '"dish":{"name":"d"},"displayNames":[{"name":"Måndagsrätt",'
                '"categoryName":"Swedish","sortOrder":1}]}')
        bad = ('{"startDate":"2026-09-%dT00:00:00Z","dishType":{"name":"N"},'
               '"dish":{"name":"d"},"displayNames":[{"name":"Rätt",'
               '"categoryName":"Swedish","sortOrder":1}]}')
        payload = ('{"data":{"dishOccurrencesByTimeRange":[%s]}}'
                   % ",".join([good] + [bad % d for d in (15, 16, 17, 18)]))
        with pytest.raises(fetch_mod.FetchError, match="unreadable"):
            _plateimpact.iter_occurrences(payload)


class TestKizuna:
    """Kizuna was missed entirely by the original restaurant search."""

    @pytest.fixture()
    def days(self):
        from scraper.restaurants import kizuna
        from pathlib import Path

        raw = (Path(__file__).parent / "fixtures" / "kizuna.html").read_text(encoding="utf-8")
        return kizuna.parse(raw)

    def test_all_five_weekdays(self, days):
        assert set(days) == {"mon", "tue", "wed", "thu", "fri"}

    def test_wrapped_dish_line_is_joined(self, days):
        """Tuesday's dish wraps as 'Dagens varmrätt' + '(Curry Kyckling donburi)'."""
        texts = [d.text for d in days["tue"]]
        assert "Dagens varmrätt (Curry Kyckling donburi)" in texts
        assert not any(t.startswith("(") for t in texts)

    def test_heading_not_captured_as_dish(self, days):
        for dishes in days.values():
            assert not any(d.text.lower() == "lunch" for d in dishes)

    def test_marked_as_static_menu(self):
        """Its rotation is fixed, so the card must not imply a fresh week."""
        from scraper.restaurants import kizuna

        assert kizuna.RESTAURANT.static_menu is True

    def test_missing_lunch_block_yields_nothing_rather_than_junk(self):
        from scraper.restaurants import kizuna

        assert kizuna.parse("<html><body><p>Stängt för renovering</p></body></html>") == {}


class TestEnglishAndSentinelTagging:
    @pytest.mark.parametrize(
        "text",
        ["Fish n chips med tartarsås", "Fish & Chips friterad fisk",
         "Shrimp salad med aioli", "Grilled salmon with potatoes"],
    )
    def test_english_fish_names_are_tagged(self, text):
        """Swedish menus mix in English dish names; these went untagged."""
        assert classify_dish(text) == "fisk"

    @pytest.mark.parametrize("text", ["Swedish meatballs", "Kycklinggryta med ris"])
    def test_english_words_do_not_false_positive(self, text):
        assert classify_dish(text) is None

    def test_no_tag_sentinel_suppresses_classification(self):
        from scraper.models import NO_TAG

        dish = Dish("Vegetarisk förrätt + oxfilé + glass", tag=NO_TAG)
        assert dish.tag == NO_TAG
        assert "tag" not in dish.to_json()

    def test_none_tag_still_auto_classifies(self):
        assert Dish("Stekt lax med dill").tag == "fisk"


class TestFoodTypes:
    """Dish food types drive the site's filter dropdown."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Focus fisksoppa med kräftstjärtar", {"fisk", "soppa"}),
            ("Krämig pestopasta med parmesan", {"pasta"}),
            ("Chicken Tikka Masala med ris", {"kyckling", "gryta"}),
            ("Sushi kockens val 11 bitar", {"sushi"}),
            ("Fläskschnitzel med rödvinssås", {"kott"}),
            ("Pokébowl", {"sallad"}),
        ],
    )
    def test_types_found(self, text, expected):
        from scraper.models import dish_types

        assert expected <= set(dish_types(text))

    def test_compound_tail_matches(self):
        """Swedish glues types onto the end of compounds."""
        from scraper.models import dish_types

        assert "soppa" in dish_types("Ärtsoppa och pannkakor")
        assert "pasta" in dish_types("Krämig pestopasta")
        assert "kott" in dish_types("Fetaostfylld nötfärsbiff")

    @pytest.mark.parametrize(
        "text,absent",
        [
            ("Flammkuchen med lök och grädde", "kott"),   # 'lamm' inside flammkuchen
            ("Rödbetsbiffar med getostkräm", "kott"),     # 'biff' inside rödbetsbiffar
        ],
    )
    def test_accidental_middles_rejected(self, text, absent):
        from scraper.models import dish_types

        assert absent not in dish_types(text)

    def test_vegetarian_dish_is_never_also_meat(self):
        """'Vegetarisk schnitzel' must not appear under the Kött filter."""
        from scraper.models import dish_types

        types = dish_types("Vegetarisk schnitzel med örtkräm", tag="veg")
        assert "veg" in types and "kott" not in types

    def test_explicit_parser_tag_is_included(self):
        """A tag the text alone cannot reveal must still be filterable."""
        from scraper.models import dish_types

        assert "veg" in dish_types("Dagens gryta med ris", tag="veg")

    def test_dish_exposes_types_in_json(self):
        dish = Dish("Ugnsbakad lax med dillsås")
        assert dish.types == ["fisk"]
        assert dish.to_json()["types"] == ["fisk"]


class TestCuisineCoverage:
    def test_every_restaurant_declares_a_cuisine(self):
        from scraper import restaurants

        missing = [m.RESTAURANT.id for m in restaurants.all_modules()
                   if not m.RESTAURANT.cuisine]
        assert not missing, f"no cuisine set: {missing}"

    def test_cuisines_come_from_a_small_stable_set(self):
        """Typos would fragment the filter dropdown into near-duplicates."""
        from scraper import restaurants

        from scraper.models import CUISINES

        found = {m.RESTAURANT.cuisine for m in restaurants.all_modules()}
        assert found <= set(CUISINES), f"unexpected labels: {found - set(CUISINES)}"
