"""Auto-discovering registry of restaurant scraper modules.

Every module in this package must define:
  RESTAURANT: models.Restaurant   — static facts (id, name, urls, walk time)
  parse(html: str) -> dict[str, list[Dish]]  — weekly menu from the page body

Optionally:
  fetch() -> str  — custom fetching (PDF extraction, JSON API, multi-page);
                    returns the text that parse() consumes.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType


def all_modules() -> list[ModuleType]:
    """Import and return every restaurant module, sorted by module name."""
    modules = []
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        modules.append(importlib.import_module(f"{__name__}.{info.name}"))
    return modules
