"""Samui Thai Kitchen — Thai lunch buffet at Engelbrektsgatan 51.

The weekly lunch buffet is published on a Gastrogate-hosted page, which is
plain server-rendered HTML: one <table class="lunch_menu"> alternating
<thead class="lunch-day-header"> (an <h3> like "Måndag 14 september") with
<tbody class="lunch-day-content"> whose <tr class="lunch-menu-item"> rows carry
the dish in <td class="td_title">.

Gastrogate publishes the coming week on a sibling URL (/lunchbuffe/1/) and marks
which week the current page shows in the week dropdown, so detect_week() reads
that label rather than trusting the page to be up to date.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import Dish, Restaurant
from ..utils import day_key, week_in_text

RESTAURANT = Restaurant(
    id="samui-thai-kitchen",
    name="Samui Thai Kitchen",
    address="Engelbrektsgatan 51, 412 52 Göteborg",
    url="https://www.samuithai.se",
    menu_url="https://samuithaiexpress.gastrogate.com/lunchbuffe/",
    walk_minutes=7,
    cuisine="Thailändskt",
    price="139 kr (buffé)",
    lunch_hours="Mån–fre 11.00–14.00",
)


def detect_week(raw: str) -> int | None:
    """ISO week the page's own week selector marks as active ("Vecka 38")."""
    soup = BeautifulSoup(raw, "lxml")
    active = soup.select_one(".menu-nav .dropdown-menu li.active a")
    return week_in_text(active.get_text(" ", strip=True)) if active else None


def parse(raw: str) -> dict[str, list[Dish]]:
    soup = BeautifulSoup(raw, "lxml")
    table = soup.select_one("table.lunch_menu")
    if table is None:
        return {}

    days: dict[str, list[Dish]] = {}
    current: str | None = None
    # thead/tbody alternate in document order: a header sets the day the rows
    # that follow belong to. A weekend header yields None, which drops its rows.
    for section in table.find_all(["thead", "tbody"]):
        classes = section.get("class") or []
        if "lunch-day-header" in classes:
            current = day_key(section.get_text(" ", strip=True))
        elif "lunch-day-content" in classes and current:
            dishes = [
                Dish(td.get_text(" ", strip=True))
                for td in section.select("td.td_title")
            ]
            dishes = [d for d in dishes if d.text]
            if dishes:
                days.setdefault(current, []).extend(dishes)

    return days
