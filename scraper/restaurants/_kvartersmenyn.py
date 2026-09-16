"""Shared extraction for menus hosted on kvartersmenyn.se.

Several restaurants publish their weekly lunch only through this aggregator.
The page wraps the menu in ``div.day div.meny`` and defends against scrapers by
injecting hidden ``<i>`` elements mid-text, which must be removed before the
text is read or dish names come out with junk spliced into them.

Each restaurant's own module keeps its line-grouping policy (category labels,
wrapped-line joining); only the site-level quirks live here.

The leading underscore keeps this module out of the auto-discovering registry.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import ValidationError


def menu_lines(html: str, expect_name: str | None = None) -> list[str]:
    """Return the menu block's non-empty text lines, decoys removed.

    Passing ``expect_name`` guards against the aggregator serving a different
    restaurant's page (it has done so after listing changes): the page title
    must contain that name, case-insensitively.
    """
    soup = BeautifulSoup(html, "lxml")

    if expect_name:
        title = soup.title.get_text() if soup.title else ""
        if expect_name.casefold() not in title.casefold():
            raise ValidationError(
                f"page does not look like {expect_name} (title: {title!r})"
            )

    meny = soup.select_one("div.day div.meny")
    if meny is None:
        return []

    # Hidden anti-scrape junk is injected as <i> elements mid-text.
    for i in meny.find_all("i"):
        i.decompose()
    for br in meny.find_all("br"):
        br.replace_with("\n")

    # Join with "" — <br> tags are already real newline nodes, and a separator
    # here would split any dish whose anti-scrape decoy sat mid-word.
    return [line.strip() for line in meny.get_text("").split("\n") if line.strip()]
