"""Frontend sanity checks: JS parses, HTML references the right files."""

import shutil
import subprocess
from pathlib import Path

import pytest

SITE = Path(__file__).parent.parent / "site"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_app_js_syntax():
    result = subprocess.run(
        ["node", "--check", str(SITE / "app.js")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_index_references_assets():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert 'src="app.js"' in html
    assert 'href="style.css"' in html
    for element_id in ("day-tabs", "filter", "cards", "status", "week-info"):
        assert f'id="{element_id}"' in html, f"missing #{element_id} used by app.js"


def test_app_js_uses_no_innerhtml():
    """Scraped third-party text must never be injected as HTML."""
    import re

    js = (SITE / "app.js").read_text(encoding="utf-8")
    assert not re.search(r"\.(innerHTML|outerHTML)\s*=", js)
    assert "insertAdjacentHTML(" not in js
    assert "document.write" not in js


def test_app_js_fetches_data_json():
    js = (SITE / "app.js").read_text(encoding="utf-8")
    assert 'fetch("data.json"' in js


def test_address_links_to_google_maps():
    """The address on each card is a Maps link, not plain text."""
    js = (SITE / "app.js").read_text(encoding="utf-8")
    assert "https://www.google.com/maps/search/?api=1&query=" in js
    assert "encodeURIComponent" in js, "map query must be URL-encoded"


def test_external_links_are_safe():
    """Every window-opening link sets rel=noopener noreferrer."""
    js = (SITE / "app.js").read_text(encoding="utf-8")
    assert js.count('target = "_blank"') == js.count('rel = "noopener noreferrer"')


def test_filter_controls_exist():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    for element_id in ("restaurant-filter", "cuisine-filter", "type-filter",
                       "clear-filters", "result-count"):
        assert f'id="{element_id}"' in html, f"missing #{element_id}"


def test_filter_ids_are_wired_in_js():
    js = (SITE / "app.js").read_text(encoding="utf-8")
    for element_id in ("restaurant-filter", "cuisine-filter", "type-filter",
                       "clear-filters", "result-count"):
        assert element_id in js, f"#{element_id} never read by app.js"
