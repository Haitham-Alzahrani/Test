"""Arabic text folding, synonym expansion and amount parsing.

Everything here is deliberately spelling-destructive.  The same `fold()` runs
at index time and at query time, which is what lets the search layer below use
a plain ``unicode61`` FTS5 tokenizer with no Arabic analyser at all: by the
time SQLite sees the text, ``مصدومة`` and ``مصدومه`` are the same bytes.
"""

from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------
# character folding
# --------------------------------------------------------------------------

# Letter-shape folding.  Saudi listings are typed on phone keyboards, and a
# fair number of them are typed on Persian/Urdu keyboards, so the lookalike
# letters below are not theoretical -- `صيانہ آتو ميتک غسالات` is a live title.
_CHAR_MAP = {
    # alef family
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ٲ": "ا", "ٳ": "ا", "ٵ": "ا",
    # ta marbuta -> ha   (مصدومة == مصدومه)
    "ة": "ه",
    # ya family          (الطائف == الطايف)
    "ى": "ي", "ئ": "ي", "ی": "ي", "ۍ": "ي", "ې": "ي", "ﻯ": "ي",
    # waw family
    "ؤ": "و", "ۆ": "و", "ۇ": "و", "ۈ": "و", "ۉ": "و", "ٶ": "و",
    # Persian / Urdu lookalikes
    "ک": "ك", "ڪ": "ك", "ګ": "ك", "گ": "ك",
    "ہ": "ه", "ھ": "ه", "ۀ": "ه",
    "ٹ": "ت", "ٿ": "ت", "ټ": "ت",
    "ڈ": "د", "ڎ": "د", "ډ": "د",
    "پ": "ب",
    "ژ": "ز", "ږ": "ر", "ڕ": "ر",
    "چ": "ج", "ڃ": "ج",
    "ڤ": "ف", "ڨ": "ف", "ڢ": "ف",
    "ں": "ن", "ڻ": "ن",
    "ۃ": "ه",
}

# Arabic-Indic (٠-٩) and Extended Arabic-Indic / Persian (۰-۹) digits.
for _i in range(10):
    _CHAR_MAP[chr(0x0660 + _i)] = str(_i)
    _CHAR_MAP[chr(0x06F0 + _i)] = str(_i)

_TRANS = str.maketrans(_CHAR_MAP)

# Harakat, tanween, superscript alef, Quranic annotation marks, tatweel.
_DIACRITICS = re.compile(
    "["
    "ؐ-ؚ"      # Arabic honorifics / signs
    "ً-ٟ"      # fathatan .. wavy hamza below
    "ٰ"             # superscript alef
    "ۖ-ۭ"      # Quranic annotation
    "ـ"             # tatweel
    "]"
)

# Zero-width joiners, bidi controls, BOM, soft hyphen.
_INVISIBLE = re.compile("[​-‏‪-‮⁦-⁩﻿­؜]")

# Hamza on its own gets dropped outright (`ماء` -> `ما`).
_HAMZA = re.compile("[ءٴٕٔ]")

# Punctuation, Arabic and Latin, plus emoji-ish symbols.  Applied *after*
# digit-separator handling so `15,000` and `1.5` survive.
_PUNCT = re.compile(
    r"[^\w\s؀-ۿ.]|_"
)

_MULTISPACE = re.compile(r"\s+")

# Collapse runs of 3+ identical characters down to 2.
#
#   كثييييير -> كثيير                (typing emphasis, safe to squash)
#
# Two deliberate exclusions:
#   * doubles are left alone -- Arabic geminates legitimately across morpheme
#     boundaries, and الممملكة -> الملكة is a real collision, not a fix;
#   * digits are left alone -- 15000 must never become 1500.
_RUNS = re.compile(r"([^\W\d_]|[^\s\d\w])\1{2,}", re.UNICODE)

# Thousands separators between digits: 15,000 -> 15000.  Decimal points
# between digits (1.5 مليون) are preserved by _PUNCT's allowlist above.
_THOUSANDS = re.compile(r"(?<=\d)[,،٬](?=\d)")
# A '.' that is not between two digits is punctuation, not a decimal point.
_STRAY_DOT = re.compile(r"(?<!\d)\.|\.(?!\d)")


def fold(text: str | None) -> str:
    """Fold `text` into the canonical form used for both indexing and querying."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", text)
    s = _INVISIBLE.sub("", s)
    s = s.translate(_TRANS)
    s = _DIACRITICS.sub("", s)
    s = _HAMZA.sub("", s)
    s = _THOUSANDS.sub("", s)      # before punctuation stripping
    s = _STRAY_DOT.sub(" ", s)     # keep 1.5, drop sentence dots
    s = _PUNCT.sub(" ", s)
    s = s.lower()
    s = _RUNS.sub(r"\1\1", s)
    s = _MULTISPACE.sub(" ", s)
    return s.strip()


def tokens(text: str | None) -> list[str]:
    """Folded whitespace tokens."""
    f = fold(text)
    return f.split() if f else []


# --------------------------------------------------------------------------
# synonyms
# --------------------------------------------------------------------------

# canonical -> variants.  Keys and values are all folded before use, so they
# can be written here in whatever spelling reads most naturally.
SYNONYMS: dict[str, list[str]] = {
    # ---- makes -------------------------------------------------------
    "فورد": ["ford", "فورد", "فرد"],
    "تويوتا": ["toyota", "تويوتا", "طويوطا", "تيوتا"],
    "شفروليه": ["chevrolet", "chevy", "شفر", "شيفروليه", "شيفي"],
    "نيسان": ["nissan", "نيسان", "نسان"],
    "دودج": ["dodge", "دودج", "دوج"],
    "جمس": ["gmc", "جمس", "جي ام سي"],
    "هوندا": ["honda", "هوندا"],
    "لكزس": ["lexus", "لكزس", "لكسس"],
    "مرسيدس": ["mercedes", "مرسيدس", "مرسدس", "بنز", "benz"],
    "كرايسلر": ["chrysler", "كرايسلر", "كرايزلر"],
    "هيونداي": ["hyundai", "هيونداي", "هونداي", "هيوانداي"],
    "كيا": ["kia", "كيا"],
    "بي ام دبليو": ["bmw", "بي ام دبليو", "بمw"],
    "ميتسوبيشي": ["mitsubishi", "ميتسوبيشي", "متسوبيشي"],
    # ---- models ------------------------------------------------------
    "f150": ["f150", "f 150", "f-150", "اف 150", "اف150", "ف150", "150", "افoneفifty"],
    "f250": ["f250", "f 250", "f-250", "اف 250"],
    "رابتر": ["raptor", "رابتر", "رابتور"],
    "اكسبديشن": ["expedition", "اكسبديشن", "اكسبيدشن", "اكسبدشن", "اكسبيديشن"],
    "لاند كروزر": ["land cruiser", "landcruiser", "لاند كروزر", "لاندكروزر", "لندكروزر", "لاند كروز"],
    "كامري": ["camry", "كامري", "كمري"],
    "كورولا": ["corolla", "كورولا", "كرولا"],
    "سلفرادو": ["silverado", "سلفرادو", "سيلفرادو"],
    "تاهو": ["tahoe", "تاهو"],
    "سوبربان": ["suburban", "سوبربان", "سبربان"],
    "هايلكس": ["hilux", "هايلكس", "هيلوكس"],
    "باترول": ["patrol", "باترول", "بترول نيسان"],
    "دورانجو": ["durango", "دورانجو", "دورانقو"],
    "شاحن": ["charger", "تشارجر", "شارجر"],
    # ---- trims / body ------------------------------------------------
    "xl": ["xl", "اكس ال"],
    "xlt": ["xlt", "اكس ال تي"],
    "لاريات": ["lariat", "لاريات", "لارييت"],
    "كينق رانش": ["king ranch", "كينق رانش", "كنق رانش", "كينج رانش"],
    "بلاتنيوم": ["platinum", "بلاتنيوم", "بلاتينيوم"],
    "fx4": ["fx4", "fx 4", "اف اكس 4"],
    # ---- drivetrain / cab (the terms that decide F-150 matches) ------
    "دبل": ["دبل", "4wd", "4x4", "دبل قير", "فور ويل", "دفع رباعي", "4 wd"],
    "غماره": ["غماره", "غمارة", "regular cab", "single cab", "غماره واحده", "استاندر", "standard cab"],
    "غماره ونص": ["غماره ونص", "غمارة ونص", "supercab", "super cab", "extended cab", "غماره و نص"],
    "غمارتين": ["غمارتين", "غمارتان", "crew cab", "supercrew", "double cab", "غمارتين كامله"],
    # ---- engines -----------------------------------------------------
    "v8": ["v8", "v 8", "ثمانيه سلندر", "8 سلندر", "ثماني سلندر", "ثمانية سلندر", "v٨"],
    "v6": ["v6", "v 6", "سته سلندر", "6 سلندر", "ست سلندر", "ستة سلندر"],
    "ايكوبوست": ["ecoboost", "ايكوبوست", "ايكو بوست", "اكوبوست", "تيربو", "turbo"],
    # ---- condition ---------------------------------------------------
    "نظيف": ["نظيف", "نظيفه", "ممتاز", "ممتازه", "حاله ممتازه", "وكاله", "شرط"],
    "مصدوم": ["مصدوم", "مصدومه", "حادث", "معدل", "تشليح", "شاصي", "مضروب", "damaged", "salvage"],
    "مستعمل": ["مستعمل", "مستخدم", "used"],
    "جديد": ["جديد", "جديده", "زيرو", "new"],
    "مطلوب": ["مطلوب", "ادور", "أدور", "ابحث", "wanted", "دور على", "ابي"],
    "على السوم": ["على السوم", "ع السوم", "السوم", "قابل للتفاوض", "قابل للنقاش", "بدل", "للبدل"],
    # ---- transmission ------------------------------------------------
    "اوتوماتيك": ["اوتوماتيك", "اتوماتيك", "اوتماتيك", "قير عادي", "automatic", "auto"],
    "عادي": ["عادي", "مانيوال", "manual", "قير عادي يدوي"],
    # ---- cities (Haraj's slugs use non-standard spellings) -----------
    "جده": ["جده", "جدة", "jeddah", "jedah"],
    "الرياض": ["الرياض", "رياض", "riyadh"],
    "الطايف": ["الطايف", "الطائف", "taif"],
    "الشرقيه": ["الشرقيه", "الشرقية", "المنطقه الشرقيه", "eastern", "الدمام", "dammam", "الخبر", "khobar"],
    "مكه": ["مكه", "مكة", "makkah", "mecca"],
    "المدينه": ["المدينه", "المدينة", "المدينه المنوره", "madinah", "medina"],
    "القصيم": ["القصيم", "بريده", "بريدة", "عنيزه", "qassim", "buraydah"],
    "ابها": ["ابها", "أبها", "abha", "عسير"],
    "حايل": ["حايل", "حائل", "hail"],
    "تبوك": ["تبوك", "tabuk"],
    "نجران": ["نجران", "najran"],
    "جازان": ["جازان", "جيزان", "jazan"],
}

_MAX_NGRAM = 3


def _build_lookup() -> dict[str, set[str]]:
    """Flatten SYNONYMS into a bidirectional folded lookup.

    Every member of a group (canonical included) maps to the whole group, so a
    query for `اكسبديشن` reaches a listing tagged `اكسبيدشن` and vice versa.
    """
    lookup: dict[str, set[str]] = {}
    for canonical, variants in SYNONYMS.items():
        group = {fold(canonical)} | {fold(v) for v in variants}
        group.discard("")
        for member in group:
            lookup.setdefault(member, set()).update(group)
    return lookup


LOOKUP = _build_lookup()


def expand(text: str | None) -> str:
    """Return the synonym expansion of `text` as a folded token string.

    Matches unigrams plus 2- and 3-grams so multi-word entries such as
    `لاند كروزر` and `على السوم` fire.  The result is stored in a *separate*
    indexed column, never merged into `norm`, so the ranker can weight an
    exact-spelling hit above a synonym hit.
    """
    toks = tokens(text)
    if not toks:
        return ""
    out: list[str] = []
    seen: set[str] = set()
    for n in range(1, _MAX_NGRAM + 1):
        for i in range(len(toks) - n + 1):
            gram = " ".join(toks[i:i + n])
            for member in LOOKUP.get(gram, ()):
                if member not in seen:
                    seen.add(member)
                    out.append(member)
    return " ".join(out)


def canonical_terms(text: str | None) -> set[str]:
    """The canonical keys whose group matched anywhere in `text`."""
    toks = tokens(text)
    hits: set[str] = set()
    canon_of = {}
    for canonical, variants in SYNONYMS.items():
        for member in {fold(canonical)} | {fold(v) for v in variants}:
            canon_of[member] = fold(canonical)
    for n in range(1, _MAX_NGRAM + 1):
        for i in range(len(toks) - n + 1):
            gram = " ".join(toks[i:i + n])
            if gram in canon_of:
                hits.add(canon_of[gram])
    return hits


# --------------------------------------------------------------------------
# amount parsing
# --------------------------------------------------------------------------

_NUM = re.compile(r"\d+(?:\.\d+)?")

_THOUSAND_WORDS = {"الف", "الاف", "ك", "k"}
_MILLION_WORDS = {"مليون", "ملايين", "m"}

_PRICE_MARKERS = {
    "سعر", "بسعر", "السعر", "ريال", "ريإل", "sar", "sr", "الحد", "حده",
    "مطلوب", "البيع", "للبيع", "نهائي", "كاش", "بكم", "بمبلغ", "المبلغ",
    "السوم", "سوم", "وصل",
}
# Markers strong enough to turn a bare 2-3 digit number into thousands.
# `للبيع` is deliberately absent: `للبيع فورد اف 150` is a model, not 150,000.
_STRONG_PRICE_MARKERS = {
    "سعر", "بسعر", "السعر", "الحد", "حده", "السوم", "سوم", "وصل",
    "بمبلغ", "المبلغ", "نهائي", "مطلوب",
}
# Tokens that make the number after them a model designation, never an amount.
_MODEL_PREFIXES = {"f", "اف", "ف", "ford", "فورد", "اف150", "f150", "f-150"}
# The narrower set that can rescue a bare 4-digit number from the year band.
# `للبيع فورد 2015` is a model year; `السعر 2000 ريال` is a price.
_CURRENCY_MARKERS = {
    "سعر", "بسعر", "السعر", "ريال", "ريإل", "sar", "sr", "الحد", "حده",
    "نهائي", "كاش", "بمبلغ", "المبلغ", "السوم", "سوم",
}
_MILEAGE_MARKERS = {
    "ممشى", "الممشى", "ماشي", "ماشيه", "عداد", "العداد", "كيلو", "كم", "km",
    "مشوار", "قاطع", "قاطعه", "mileage",
}
_YEAR_MARKERS = {"موديل", "الموديل", "مديل", "المديل", "model", "سنه", "سنة", "عام", "ألموديل"}
_PHONE_MARKERS = {"جوال", "واتس", "اتصال", "تواصل", "رقم", "هاتف", "واتساب", "الجوال"}

_PHONE_RE = re.compile(
    r"(?<!\d)(?:00966|\+?966)?[\s\-]?0?5\d(?:[\s\-]?\d){7}(?!\d)"
)

# Marker words are matched against *folded* tokens, so they must be folded too
# (`الممشى` folds to `الممشي`, `سنة` to `سنه`).
_THOUSAND_WORDS = {fold(w) for w in _THOUSAND_WORDS}
_MILLION_WORDS = {fold(w) for w in _MILLION_WORDS}
_PRICE_MARKERS = {fold(w) for w in _PRICE_MARKERS}
_CURRENCY_MARKERS = {fold(w) for w in _CURRENCY_MARKERS}
_STRONG_PRICE_MARKERS = {fold(w) for w in _STRONG_PRICE_MARKERS}
_MODEL_PREFIXES = {fold(w) for w in _MODEL_PREFIXES}
_MILEAGE_MARKERS = {fold(w) for w in _MILEAGE_MARKERS}
_YEAR_MARKERS = {fold(w) for w in _YEAR_MARKERS}
_PHONE_MARKERS = {fold(w) for w in _PHONE_MARKERS}


def _multiplier(after: list[str], base: float) -> int:
    """Thousands / millions multiplier following a number.

    A multiplier word after a number that is already >= 1000 is emphasis, not
    arithmetic: `الحد 52000 آلاف` is 52,000 SAR, not 52 million.
    """
    if base >= 1_000:
        return 1
    for t in after[:2]:
        if t in _THOUSAND_WORDS:
            return 1_000
        if t in _MILLION_WORDS:
            return 1_000_000
    return 1


def _nearest_marker(toks: list[str], i: int, radius: int = 3) -> tuple[str | None, int]:
    """Which marker owns the number at `toks[i]`, and how far away it is.

    Returns ``("price"|"mileage"|None, distance)``.  The nearest marker wins;
    on a tie the *preceding* one wins, because Arabic listings lead with the
    label far more often than they trail it (`بسعر 45 ألف`, `ماشي 475الف`).
    Distance matters: in `... اف 150 الموديل 2013 العداد 332،000 كيلو` the
    number 150 is three tokens from `العداد` and 332,000 is one token from it,
    and only the closer binding is the real mileage.
    """
    def kind_of(tok: str) -> str | None:
        if tok in _MILEAGE_MARKERS:
            return "mileage"
        if tok in _PRICE_MARKERS:
            return "price"
        return None

    for dist in range(1, radius + 1):
        if i - dist >= 0:
            k = kind_of(toks[i - dist])
            if k:
                return k, dist
        if i + dist < len(toks):
            k = kind_of(toks[i + dist])
            if k:
                return k, dist
    return None, 0


def _adjacent_strong_price(toks: list[str], i: int) -> bool:
    """True when a strong price marker sits directly beside `toks[i]`."""
    for j in (i - 1, i + 1):
        if 0 <= j < len(toks) and toks[j] in _STRONG_PRICE_MARKERS:
            return True
    return False


# How strongly a marker binds a number, by token distance.
_MARKER_WEIGHT = {1: 6.0, 2: 4.0, 3: 2.0}


def parse_amount(text: str | None, kind: str = "price") -> int | None:
    """Score every number in `text` and return the best candidate for `kind`.

    Listing bodies are decoy-rich: `موديل 2012` is a year, `0501234567` is a
    phone number, `ماشي 475الف` is mileage and `بسعر 45 ألف` is the price, and
    they routinely all appear in the same paragraph.  Taking the first number
    gets this wrong most of the time, so every number is scored against its
    surrounding words and the winner is returned.

    `kind` is either ``"price"`` (SAR) or ``"mileage"`` (kilometres).
    """
    f = fold(text)
    if not f:
        return None

    # Kill phone numbers before tokenising -- they are the loudest decoy.
    f = _PHONE_RE.sub(" ", f)

    toks = f.split()
    best: tuple[float, int] | None = None

    for i, tok in enumerate(toks):
        for m in _NUM.finditer(tok):
            # A number glued to letters on its left is a designation, not an
            # amount: `f150`, `اف150`, `c300`.
            if m.start() > 0 and tok[m.start() - 1].isalpha():
                continue
            raw = float(m.group())
            trailing = tok[m.end():]            # `475الف` -- glued multiplier
            after = ([trailing] if trailing else []) + toks[i + 1:i + 3]
            before = toks[max(0, i - 3):i]
            ctx = set(before) | set(t for t in after if t)

            # `فورد اف 150` / `f 150` -- the model number, split by folding.
            if i > 0 and toks[i - 1] in _MODEL_PREFIXES:
                continue

            mult = _multiplier([t for t in after if t], raw)
            value = raw * mult
            if value <= 0:
                continue

            digits = m.group().split(".")[0]

            # A bare 4-digit number in the model-year band is a year unless a
            # currency marker is attached.
            if len(digits) == 4 and mult == 1 and 1950 <= raw <= 2035:
                if not (ctx & _CURRENCY_MARKERS):
                    continue
            if ctx & _YEAR_MARKERS and mult == 1 and 1950 <= raw <= 2035:
                continue
            if ctx & _PHONE_MARKERS and len(digits) >= 7:
                continue

            # A glued multiplier binds tighter than any nearby word.
            if trailing in _THOUSAND_WORDS or trailing in _MILLION_WORDS:
                owner, dist = _nearest_marker(toks, i, radius=2)
            else:
                owner, dist = _nearest_marker(toks, i)

            score = 0.0
            if owner == kind:
                score += _MARKER_WEIGHT.get(dist, 1.0)
            elif owner is not None:
                continue                        # owned by the other field
            if mult > 1:
                score += 1.5

            if kind == "price":
                if (mult == 1 and 20 <= value <= 999 and owner == "price"
                        and _adjacent_strong_price(toks, i)):
                    value *= 1_000
                if 3_000 <= value <= 3_000_000:
                    score += 2
                else:
                    score -= 3
            else:
                # Bare 2-3 digit mileages on Haraj are in thousands:
                # `الممشى 300` means 300,000 km.
                if mult == 1 and 20 <= value <= 999 and owner == "mileage":
                    value *= 1_000
                if 10_000 <= value <= 900_000:
                    score += 2
                else:
                    score -= 3

            if score <= 0:
                continue
            cand = (score, int(value))
            if best is None or cand[0] > best[0]:
                best = cand

    return best[1] if best else None


def parse_price(text: str | None) -> int | None:
    return parse_amount(text, "price")


def parse_mileage(text: str | None) -> int | None:
    return parse_amount(text, "mileage")


# --------------------------------------------------------------------------
# structured attribute block
# --------------------------------------------------------------------------

# Haraj prepends a structured block to car listings.  English mirror:
#
#     XL 2014 Used
#     Automatic
#     Gasoline
#     mileage: 130 KM
#     4WD
#
# Arabic original:
#
#     كرايزلر C300 2017 مستخدم
#     قير اوتماتيك
#     بنزين
#     الممشى: 260 ألف كيلو
#     دبل
#
# The mileage figure is in THOUSANDS in both mirrors -- `mileage: 130 KM` is
# 130,000 km, not 130 km.  Parsing it literally makes every truck on the site
# look nearly new.
_MILEAGE_BLOCK = re.compile(
    r"(?:mileage|الممشى|الممشي|ممشى)\s*:?\s*(\d+(?:\.\d+)?)\s*"
    r"(الف|ألف|thousand|k)?\s*(?:كيلو|km|كم)?",
    re.IGNORECASE,
)


def parse_block_mileage(text: str | None) -> int | None:
    """Parse the structured block's mileage field, in real kilometres."""
    if not text:
        return None
    m = _MILEAGE_BLOCK.search(text)
    if not m:
        return None
    value = float(m.group(1))
    # The field is always expressed in thousands, whether or not the page
    # spells out `ألف` / `thousand`.
    return int(value * 1_000)
