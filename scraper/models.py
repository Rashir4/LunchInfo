"""Data model for restaurants and their weekly lunch menus."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri")

SWEDISH_DAYS = {
    "måndag": "mon",
    "tisdag": "tue",
    "onsdag": "wed",
    "torsdag": "thu",
    "fredag": "fri",
}

# Dish tagging. Swedish lunch menus name several proteins in one line ("Fläsk-
# schnitzel ... med ansjovis och kapris"), so a plain keyword hit is not enough:
# the protein named FIRST is the dish, the rest are garnish. classify_dish picks
# whichever keyword family appears earliest, with one override — an explicit
# vegetarian/vegan label anywhere wins, because that is the kitchen's own word
# for the dish ("Vegetarisk schnitzel" is vegetarian, schnitzel notwithstanding).

# Explicit kitchen labels. These override position entirely.
VEG_LABELS = (
    "vegetarisk", "vegetariskt", "vegetariska", "vegansk", "veganskt",
    "veganska", "vegan", "veg:", "veg :",
)

FISH_WORDS = (
    "fisk", "lax", "torsk", "sej", "räk", "skaldjur", "sill", "strömming",
    "kolja", "rödspätta", "spätta", "gös", "hälleflundra", "mussl", "mussel",
    "tonfisk", "abborre", "makrill", "ansjovis", "anjovis", "sardell",
    "krabba", "hummer", "lubb", "sjötunga", "kräft", "böckling", "marulk",
    "kummel", "piggvar", "sik ", "ål ", "rödtunga", "havskatt", "pangasius",
    "sejrygg", "flundra", "rocka", "bläckfisk", "calamares", "scampi",
    "regnbåg", "öring", "röding", "forell", "siklöja", "vitling", "surimi",
    "skagenröra", "skagen",
    # Swedish menus mix in English dish names ("Fish n chips", "Shrimp salad").
    "fish", "salmon", "shrimp", "prawn", "tuna", "seafood", "cod ",
    # How Swedish menus name fish without naming the species.
    "dagens fångst", "havets", "fångst",
)

# Note: no bare "nöt" (matches "nötter", nuts) and no "raggmunk" (a potato
# pancake — vegetarian on its own, even though it is usually served with pork).
MEAT_WORDS = (
    "kyckling", "fläsk", "nötkött", "nötfärs", "oxe", "oxfilé", "oxhögrev",
    "oxbringa", "biff", "kalv", "lamm", "korv", "bacon", "skinka", "köttbull",
    "köttfärs", "schnitzel", "kassler", "revben", "kalkon", "anka", "högrev",
    "karré", "wallenbergare", "isterband", "prinskorv", "salami", "kebab",
    "kött", "chorizo", "pancetta", "entrecôte", "ryggbiff", "fläskfilé",
)

# Meat-free proteins. Weaker than a label, but they identify the dish when no
# meat or fish is named earlier ("Quorn-biff" is vegetarian, "biff" and all).
#
# Deliberately NOT listed: ingredient words like svamp, aubergine, gnocchi or
# getost. A mushroom pasta may still arrive with pancetta, and a badge that
# wrongly promises vegetarian is worse than no badge — someone avoiding meat
# acts on it. Untagged means "unknown", which the card presents honestly.
VEG_WORDS = (
    "falafel", "halloumi", "quorn", "tofu", "sojabiff", "sojafärs",
    "grönsaksbiff", "linsgryta", "kikärt", "seitan", "tempeh",
)


def _compile(words: tuple[str, ...]) -> re.Pattern:
    """Match any keyword starting at a word boundary.

    A trailing boundary is deliberately not required: Swedish glues compounds
    together, so "lax" must also match "laxfilé". A LEADING boundary is required
    so "sej" does not match inside "serveras".
    """
    alts = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<![a-zåäö])(?:{alts})")


def _compile_compound(words: tuple[str, ...]) -> re.Pattern:
    """Like _compile, but also matches a keyword that ENDS a Swedish compound.

    Food types hide at the tail of compounds ("fisksoppa", "pestopasta",
    "nötfärsbiff"), which a leading-boundary-only match misses. Requiring a
    boundary on EITHER side still rejects the accidental middles that plain
    substring matching would catch — "lamm" inside "flammkuchen", "biff"
    inside "rödbetsbiffar".
    """
    alts = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?:(?<![a-zåäö])(?:{alts})|(?:{alts})(?![a-zåäö]))")


_PATTERN_CACHE: dict[tuple, re.Pattern] = {}


def _pattern(words) -> re.Pattern:
    """Cached compound-aware keyword matcher, for food types."""
    key = tuple(words)
    if key not in _PATTERN_CACHE:
        _PATTERN_CACHE[key] = _compile_compound(key)
    return _PATTERN_CACHE[key]


_VEG_LABEL_RE = _compile(VEG_LABELS)
_FISH_RE = _compile(FISH_WORDS)
_MEAT_RE = _compile(MEAT_WORDS)
_VEG_RE = _compile(VEG_WORDS)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class ValidationError(Exception):
    """Raised when scraped data fails sanity checks."""


def clean_text(text: str) -> str:
    """Normalize scraped text: strip tags, collapse whitespace, trim junk."""
    text = _TAG_RE.sub(" ", text)
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = _WS_RE.sub(" ", text).strip()
    # Drop leading bullet/dash decorations left over from markup.
    text = text.lstrip("•·-–—* ").strip()
    return text


def classify_dish(text: str) -> str | None:
    """Best-effort dish tag ('veg' / 'fisk'); None when it is neither or unclear."""
    low = text.lower()
    if _VEG_LABEL_RE.search(low):
        return "veg"

    # Earliest-named protein wins; later ones are garnish.
    candidates = []
    for tag, pattern in (("fisk", _FISH_RE), (None, _MEAT_RE), ("veg", _VEG_RE)):
        m = pattern.search(low)
        if m:
            candidates.append((m.start(), tag))
    if not candidates:
        return None
    return min(candidates)[1]


# Food types used by the site's filter. Broader than the veg/fisk badge: a dish
# can have several (a "fisksoppa" is both fisk and soppa), and "kott"/"kyckling"
# get their own entries so someone can filter FOR meat, not just away from it.
# Keys are the stable ids stored in data.json; the UI owns the Swedish labels.
FOOD_TYPE_WORDS = {
    "kyckling": ("kyckling", "kalkon", "chicken", "tikka", "tandoori"),
    "kott": (
        "fläsk", "nötkött", "nötfärs", "oxe", "oxfilé", "oxhögrev", "oxbringa",
        "biff", "kalv", "lamm", "korv", "bacon", "skinka", "köttbull", "köttfärs",
        "schnitzel", "kassler", "revben", "anka", "högrev", "karré", "kött",
        "wallenbergare", "isterband", "pluma", "entrecôte", "ryggbiff", "kalops",
        "pulled pork", "chorizo", "beef", "pork", "kåldolmar", "pannbiff", "pytt",
    ),
    "pasta": (
        "pasta", "spaghetti", "lasagne", "tagliatelle", "rigatoni", "penne",
        "gnocchi", "risotto", "pizza", "carbonara", "ravioli", "tortellini",
        "linguine", "fettuccine", "macaroni", "makaroner",
    ),
    "soppa": ("soppa", "buljong", "ramen", "soup", "bouillabaise", "bouillabaisse"),
    "sallad": ("sallad", "salad", "bowl", "poké", "poke"),
    "sushi": ("sushi", "maki", "nigiri", "sashimi"),
    "burgare": ("burgare", "burger", "hamburgare"),
    "nudlar": ("nudlar", "noodle", "wok", "udon", "pad thai", "pad ", "bún", "bun cha"),
    "gryta": ("gryta", "curry", "masala", "vindaloo", "korma", "stuvning", "ragu"),
}

# The kitchen filter's vocabulary. Kept small and closed on purpose: a
# near-duplicate ("Svenskt" beside "Husmanskost") would split one group into two
# dropdown entries, so a new label belongs here only when nothing existing fits.
CUISINES = (
    "Husmanskost", "Modern svenskt", "Varierat", "Fisk & skaldjur",
    "Italienskt", "Franskt", "Amerikanskt", "Mexikanskt",
    "Indiskt", "Thailändskt", "Vietnamesiskt", "Japanskt", "Kinesiskt",
    "Asiatiskt", "Vegetariskt",
)

# Ordered so the filter dropdown reads sensibly; veg/fisk come from the badge.
FOOD_TYPES = ("veg", "fisk", "kott", "kyckling", "gryta", "pasta",
              "soppa", "sallad", "sushi", "nudlar", "burgare")


def dish_types(text: str, tag: str | None = None) -> list[str]:
    """Every food type a dish belongs to, for filtering.

    `tag` None means "work the badge out from the text", so this is usable
    standalone; NO_TAG ("") means a parser deliberately suppressed the badge and
    no veg/fisk type is added; an explicit "veg"/"fisk" is honoured as given,
    which is how a tag the text cannot reveal still reaches the filter.
    """
    low = text.lower()
    found = {t for t, words in FOOD_TYPE_WORDS.items() if _pattern(words).search(low)}
    badge = classify_dish(text) if tag is None else tag
    if badge:
        found.add(badge)
    # A dish the kitchen calls vegetarian is not also "meat" because it mimics
    # one ("vegetarisk schnitzel", "sojabiff").
    if "veg" in found:
        found -= {"kott", "kyckling"}
    return [t for t in FOOD_TYPES if t in found]


# Pass as Dish(text, tag=NO_TAG) to suppress automatic classification, for a
# dish whose text would be misread — e.g. a multi-course plate whose LAST course
# is the vegetarian one, where classifying the whole string would mislabel it.
# Distinct from None, which means "classify this for me".
NO_TAG = ""


@dataclass
class Dish:
    text: str
    tag: str | None = None

    types: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.text = clean_text(self.text)
        if self.tag is None:
            self.tag = classify_dish(self.text)
        self.types = dish_types(self.text, self.tag)

    def validate(self) -> None:
        if not self.text:
            raise ValidationError("empty dish text")
        if len(self.text) < 3:
            raise ValidationError(f"suspiciously short dish text: {self.text!r}")
        if len(self.text) > 300:
            raise ValidationError(f"suspiciously long dish text ({len(self.text)} chars)")
        if "<" in self.text and ">" in self.text:
            raise ValidationError(f"HTML leaked into dish text: {self.text!r}")

    def to_json(self) -> dict:
        out: dict = {"text": self.text}
        if self.tag:
            out["tag"] = self.tag
        if self.types:
            out["types"] = self.types
        return out


@dataclass
class Restaurant:
    """Static facts about one restaurant. Parsers fill in the weekly menu."""

    id: str
    name: str
    address: str
    url: str          # restaurant home page
    menu_url: str     # page the weekly menu is scraped from
    walk_minutes: int
    price: str = ""
    lunch_hours: str = ""
    cuisine: str = ""   # one of models.CUISINES; drives the site's kitchen filter
    # True when the weekday rotation is fixed rather than changing weekly. The
    # card says so, since "veckans lunch" would otherwise overpromise.
    static_menu: bool = False
    # day key -> list of dishes; empty dict means scrape failed / no menu
    days: dict[str, list[Dish]] = field(default_factory=dict)
    error: str | None = None
    # ISO week the source page claims, when it says so and it is NOT the
    # current week. Set by main.py from a parser's optional detect_week();
    # the frontend shows it so a stale menu is never passed off as this week's.
    stale_week: int | None = None

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z0-9-]+", self.id):
            raise ValidationError(f"bad restaurant id: {self.id!r}")
        if not self.name or not self.menu_url.startswith("http"):
            raise ValidationError(f"{self.id}: missing name or menu_url")
        if not 1 <= self.walk_minutes <= 25:
            raise ValidationError(f"{self.id}: walk_minutes out of range")
        if self.cuisine and self.cuisine not in CUISINES:
            raise ValidationError(
                f"{self.id}: unknown cuisine {self.cuisine!r} — add it to "
                "models.CUISINES only if no existing label fits"
            )
        for day, dishes in self.days.items():
            if day not in WEEKDAYS:
                raise ValidationError(f"{self.id}: unknown day key {day!r}")
            for dish in dishes:
                try:
                    dish.validate()
                except ValidationError as exc:
                    raise ValidationError(f"{self.id}/{day}: {exc}") from exc

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "url": self.url,
            "menu_url": self.menu_url,
            "walk_minutes": self.walk_minutes,
            "price": self.price,
            "lunch_hours": self.lunch_hours,
            "cuisine": self.cuisine,
            "static_menu": self.static_menu,
            "days": {d: [dish.to_json() for dish in dishes] for d, dishes in self.days.items()},
            "error": self.error,
            "stale_week": self.stale_week,
        }
