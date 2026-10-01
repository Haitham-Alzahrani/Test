"""Natural-language memory extraction (Arabic + English).

Converts messages such as

* ``"Mutiny عجبني لأن التمثيل والقصه والاحداث والتسلسل ممتازه"``
* ``"The Amateur بطيء جدًا ومللت منه من أول عشر دقائق"``
* ``"اكمل"`` / ``"ضعه للمشاهدة لاحقًا"`` / ``"لا يعجبني الممثلين"``

into a structured :class:`ParsedMessage`.  Parsing is rule-based and deterministic so the same
sentence always produces the same memory update.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from mris.memory.vocabulary import (
    ASPECT_WORDS,
    CONTRAST_MARKERS,
    DEAD_EXPANSION,
    INHERENT_NEGATIVE,
    INHERENT_POSITIVE,
    OPENING_MARKERS,
)
from mris.text import normalize_text

INTENT_CONTINUE = "continue"
INTENT_RECOMMEND = "recommend"
INTENT_FEEDBACK = "feedback"
INTENT_WATCH_LATER = "watch_later"
INTENT_CAST_REJECT = "cast_reject"
INTENT_PREFERENCE = "preference"
INTENT_UNKNOWN = "unknown"


def _n(*phrases: str) -> list[str]:
    return [normalize_text(p) for p in phrases]


CONTINUE_PHRASES = _n("اكمل", "استمر", "كمل", "واصل", "التالي", "continue", "keep going", "next", "go on")
RECOMMEND_PHRASES = _n(
    "اقترح",
    "رشح",
    "ترشيح",
    "اعطني فيلم",
    "عطني فيلم",
    "ابي فيلم",
    "ابغى فيلم",
    "مضمون",
    "recommend",
    "suggest",
    "give me a movie",
)
WATCH_LATER_PHRASES = _n(
    "للمشاهده لاحقا",
    "للمشاهده لاحقًا",
    "لاحقا",
    "بعدين",
    "قائمه المشاهده",
    "احفظه",
    "خله عندي",
    "watch later",
    "watchlist",
    "save it for later",
    "keep it for later",
)
CAST_REJECT_PHRASES = _n(
    "لا يعجبني الممثلين",
    "ما يعجبني الممثلين",
    "ما عجبني الممثلين",
    "الممثلين ما عجبوني",
    "ما احب الممثلين",
    "ما حبيت الممثلين",
    "الممثلين ما يعجبوني",
    "don't like the actors",
    "dont like the actors",
    "don't like the cast",
    "dont like the cast",
    "actors didn't appeal",
)
DISLIKED_PHRASES = _n(
    "ما عجبني",
    "لم يعجبني",
    "ما اعجبني",
    "ما يعجبني",
    "مو حلو",
    "ماهو حلو",
    "سيء",
    "سيئ",
    "زفت",
    "خايس",
    "ما حبيته",
    "كرهته",
    "disliked",
    "didn't like",
    "did not like",
    "didnt like",
    "hated",
    "bad movie",
    "terrible",
)
MEDIUM_PHRASES = _n(
    "متوسط", "عادي", "نص نص", "مقبول", "average", "medium", "it was ok", "it was okay", "meh", "so so"
)
LOVED_PHRASES = _n(
    "عجبني جدا",
    "اعجبني جدا",
    "عجبني مره",
    "اعجبني كثير",
    "عجبني كثير",
    "حبيته مره",
    "رهيب",
    "خرافي",
    "ممتاز",
    "روعه",
    "جبار",
    "قمه",
    "اسطوري",
    "loved",
    "excellent",
    "amazing",
    "fantastic",
    "masterpiece",
    "loved it",
)
LIKED_PHRASES = _n(
    "عجبني", "اعجبني", "حبيته", "حلو", "جيد", "زين", "كويس", "liked", "good", "enjoyed", "nice"
)
WATCHED_PHRASES = _n("شاهدته", "شفته", "تابعته", "خلصته", "watched", "saw it", "seen it")
PREFERENCE_PHRASES = _n(
    "لا اريد", "ما ابي", "ما ابغى", "لا ابي", "لا ابغى", "ابي شي", "اريد شي", "i don't want", "i want"
)
UNIVERSAL_ACTOR_PHRASES = _n(
    "في اي فيلم", "بشكل عام", "كل افلامه", "دايما", "any movie", "in general", "never again"
)

_RATING_NUMBER = re.compile(r"(\d+(?:[.,]\d)?)\s*(?:من|/|out of)\s*10\b")
_YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
_LATIN_TITLE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 :'’&.,!\-]*[A-Za-z0-9!]|[A-Za-z]")
_ENGLISH_STOP = set(
    "i the a it was is and but too much very really so movie film this that loved liked disliked hated good bad "
    "great boring slow acting story continue watch later recommend average medium excellent amazing ok okay".split()
)


@dataclass
class ParsedMessage:
    intent: str
    raw: str
    title: str | None = None
    year: int | None = None
    rating_label: str | None = None
    rating_value: float | None = None
    positive_traits: list[str] = field(default_factory=list)
    negative_traits: list[str] = field(default_factory=list)
    refers_to_last: bool = False
    universal_actor: bool = False
    watched: bool = False


_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    # Arabic attaches conjunctions/prepositions to words: "والقصه" = "و" + "القصه"
    if phrase not in _PATTERN_CACHE:
        _PATTERN_CACHE[phrase] = re.compile(r"(?:^|\s)(?:[وفبلك])?" + re.escape(phrase) + r"(?=\s|$)")
    return _PATTERN_CACHE[phrase]


def _contains(text: str, phrases: list[str]) -> bool:
    return any(_phrase_pattern(p).search(text) for p in phrases if p)


def _rating_from_value(value: float) -> str:
    if value >= 8.5:
        return "loved"
    if value >= 6.5:
        return "good"
    if value >= 5:
        return "medium"
    return "disliked"


def detect_rating(norm: str) -> tuple[str | None, float | None]:
    value = None
    if m := _RATING_NUMBER.search(norm):
        value = float(m.group(1).replace(",", "."))
    if _contains(norm, MEDIUM_PHRASES):
        # "عادي، ما عجبني التصوير" = average overall with one specific complaint
        return "medium", value
    if _contains(norm, DISLIKED_PHRASES):
        return "disliked", value
    if value is not None:
        return _rating_from_value(value), value
    if _contains(norm, LOVED_PHRASES):
        return "loved", value
    # "عجبني لأن التمثيل ... ممتازه" -> loved (praise + superlative)
    if _contains(norm, LIKED_PHRASES):
        return "liked", value
    return None, value


_NEGATIVE_ASPECT = {
    "strong_acting": "weak_cast",
    "strong_story": "weak_story",
    "event_quality": "weak_events",
    "event_progression": "weak_progression",
    "coherence": "confusing_story",
    "strong_opening": "slow_opening",
    "action": "weak_action",
    "strong_tension": "weak_tension",
    "strong_production": "low_production",
    "cinematography": "chaotic_camera",
    "fast_pacing": "slow_pacing",
}
_POSITIVE_ASPECT = {"cinematography": "good_cinematography"}


def extract_traits(norm: str, polarity: int) -> tuple[list[str], list[str]]:
    """Return (positive_traits, negative_traits) found in normalised text."""
    pos: list[str] = []
    neg: list[str] = []
    segments = [norm]
    for marker in CONTRAST_MARKERS:
        if f" {marker} " in f" {norm} ":
            head, _, tail = f" {norm} ".partition(f" {marker} ")
            segments = [head.strip(), tail.strip()]
            break
    for idx, seg in enumerate(segments):
        seg_pol = polarity if idx == 0 else -polarity if polarity else -1
        for trait, words in INHERENT_NEGATIVE.items():
            if _contains(seg, words):
                neg.append(trait)
        for trait, words in INHERENT_POSITIVE.items():
            if _contains(seg, words):
                pos.append(trait)
        if seg_pol == 0:
            continue
        for trait, words in ASPECT_WORDS.items():
            if _contains(seg, words):
                if seg_pol > 0:
                    pos.append(_POSITIVE_ASPECT.get(trait, trait))
                else:
                    neg.append(_NEGATIVE_ASPECT.get(trait, trait))
    if ("slow_pacing" in neg or "boring" in neg) and _contains(norm, OPENING_MARKERS):
        neg += ["slow_opening", "low_initial_engagement"]
    if "boring" in neg:
        neg.append("slow_pacing")
    if "low_energy" in neg:
        neg += DEAD_EXPANSION
    # a trait cannot be both: explicit negatives win
    pos = [t for t in dict.fromkeys(pos) if t not in neg]
    neg = list(dict.fromkeys(t for t in neg if t != "boring"))
    return pos, neg


def find_title(raw: str, known_titles: list[tuple[str, object]] | None = None) -> str | None:
    norm = f" {normalize_text(raw)} "
    for key, _movie in known_titles or []:
        if key and len(key) >= 3 and f" {key} " in norm:
            return key
    candidates = []
    for m in _LATIN_TITLE.finditer(raw):
        chunk = _YEAR.sub("", m.group(0)).strip(" .,:!-")
        words = [w for w in re.split(r"\s+", chunk) if w]
        if words and not all(w.lower().strip(".,!") in _ENGLISH_STOP for w in words) and not chunk.isdigit():
            candidates.append(chunk)
    if not candidates:
        return None
    # an Arabic sentence with an English title: the Latin run *is* the title
    if re.search(r"[؀-ۿ]", raw):
        return max(candidates, key=len)
    return None


def parse_message(raw: str, known_titles: list[tuple[str, object]] | None = None) -> ParsedMessage:
    norm = normalize_text(raw)
    title = find_title(raw, known_titles)
    year_match = _YEAR.search(raw)
    year = int(year_match.group(1)) if year_match else None
    watched = _contains(norm, WATCHED_PHRASES)

    if _contains(norm, CAST_REJECT_PHRASES):
        return ParsedMessage(
            INTENT_CAST_REJECT,
            raw,
            title=title,
            year=year,
            negative_traits=["cast_mismatch"],
            refers_to_last=title is None,
            universal_actor=_contains(norm, UNIVERSAL_ACTOR_PHRASES),
        )
    if _contains(norm, WATCH_LATER_PHRASES):
        return ParsedMessage(INTENT_WATCH_LATER, raw, title=title, year=year, refers_to_last=title is None)

    rating, value = detect_rating(norm)
    if rating is None and _contains(norm, PREFERENCE_PHRASES):
        pos, neg = extract_traits(norm, 0)
        if pos or neg:
            negated = _contains(norm, _n("لا اريد", "ما ابي", "ما ابغى", "لا ابي", "لا ابغى", "i don't want"))
            if negated:  # "لا اريد شي ميت" -> everything mentioned is something to avoid
                neg, pos = list(dict.fromkeys(neg + [p for p in pos])), []
            return ParsedMessage(INTENT_PREFERENCE, raw, positive_traits=pos, negative_traits=neg)

    if rating is None and (watched or title):
        pos, neg = extract_traits(norm, 0)
        if neg and not pos:
            rating = "disliked"
        elif pos and not neg:
            rating = "liked"
    if rating is not None:
        polarity = {"loved": 1, "liked": 1, "good": 1, "medium": 0, "disliked": -1}[rating]
        pos, neg = extract_traits(norm, polarity)
        if (
            rating == "liked"
            and len(pos) >= 3
            and not neg
            and _contains(norm, _n("ممتاز", "ممتازه", "excellent"))
        ):
            rating = "loved"
        return ParsedMessage(
            INTENT_FEEDBACK,
            raw,
            title=title,
            year=year,
            rating_label=rating,
            rating_value=value,
            positive_traits=pos,
            negative_traits=neg,
            refers_to_last=title is None,
            watched=True,
        )

    if _contains(norm, CONTINUE_PHRASES):
        return ParsedMessage(INTENT_CONTINUE, raw, year=year)
    if _contains(norm, RECOMMEND_PHRASES):
        return ParsedMessage(INTENT_RECOMMEND, raw)
    return ParsedMessage(INTENT_UNKNOWN, raw, title=title, year=year)
