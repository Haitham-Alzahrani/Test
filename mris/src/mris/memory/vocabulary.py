"""Trait vocabulary: maps characteristic phrases (English seed data, Arabic/English feedback)
to the canonical trait keys used by similarity, learning and penalties."""

from __future__ import annotations

from mris.text import normalize_text

# English characteristic phrases (as written in reference data) -> traits
CHARACTERISTIC_TRAITS: dict[str, list[str]] = {
    "realistic survival": ["realistic", "survival"],
    "offshore": ["offshore"],
    "rescue": ["rescue"],
    "time pressure": ["time_pressure"],
    "continuous danger": ["immediate_danger", "continuous_events", "strong_tension"],
    "strong tension": ["strong_tension"],
    "serious tone": ["serious_tone"],
    "fast pacing": ["fast_pacing"],
    "immediate danger": ["immediate_danger", "strong_opening"],
    "pursuit": ["pursuit"],
    "continuous movement": ["continuous_events", "fast_pacing"],
    "modern": ["modern_setting"],
    "entertaining": ["entertaining"],
    "strong acting": ["strong_acting"],
    "strong story": ["strong_story"],
    "excellent event progression": ["event_progression", "continuous_events"],
    "clear plot": ["clear_story"],
    "action": ["action"],
    "crime": ["crime"],
    "strong production": ["strong_production"],
    "good opening": ["strong_opening"],
    "modern crime": ["crime", "modern_setting"],
    "heist": ["heist", "crime"],
    "movement": ["continuous_events"],
    "chaos": ["chaotic_energy"],
    "strong execution": ["strong_production", "entertaining"],
    "realistic action": ["realistic", "action", "clear_action"],
    "revenge": ["revenge"],
    "immediate conflict": ["strong_opening", "immediate_danger"],
    "clear objective": ["clear_story"],
    "industrial disaster": ["industrial_disaster", "disaster"],
    "evacuation": ["escape", "survival"],
    "survival": ["survival"],
    "realistic danger": ["realistic", "immediate_danger"],
    "protection": ["protector"],
    "hostage": ["hostage"],
    "police action": ["police", "action"],
}


def characteristics_to_traits(characteristics: list[str]) -> dict[str, float]:
    traits: dict[str, float] = {}
    for c in characteristics:
        key = c.strip().lower()
        for trait in CHARACTERISTIC_TRAITS.get(key, [key.replace(" ", "_").replace("-", "_")]):
            traits[trait] = 1.0
    return traits


def _n(*phrases: str) -> list[str]:
    return [normalize_text(p) for p in phrases]


# Aspect words whose polarity follows the sentence (positive in praise, negative in complaints)
ASPECT_WORDS: dict[str, list[str]] = {
    "strong_acting": _n("التمثيل", "الممثلين", "الاداء", "acting", "performances", "cast"),
    "strong_story": _n("القصه", "القصة", "الحبكه", "story", "plot"),
    "event_quality": _n("الاحداث", "events"),
    "event_progression": _n("التسلسل", "تسلسل", "progression", "sequence of events"),
    "coherence": _n("التسلسل", "منطقي", "مترابط", "coherent", "logical"),
    "strong_opening": _n("البدايه", "البداية", "opening", "beginning", "start"),
    "action": _n("الاكشن", "action"),
    "strong_tension": _n("التشويق", "الاثاره", "التوتر", "tension", "suspense"),
    "strong_production": _n("الانتاج", "production"),
    "cinematography": _n(
        "التصوير", "الكاميرا", "الاخراج", "cinematography", "filming", "camera", "directing"
    ),
    "fast_pacing": _n("الريتم", "الايقاع", "pacing", "pace"),
}

# Traits that carry their own polarity regardless of the overall rating
INHERENT_POSITIVE: dict[str, list[str]] = {
    "fast_pacing": _n("سريع", "سريعه", "fast paced", "fast"),
    "entertaining": _n("ممتع", "ممتعه", "entertaining", "fun"),
    "realistic": _n("واقعي", "واقعيه", "realistic"),
    "strong_tension": _n("مشوق", "مشوقه", "حماس", "حماسي", "يحبس الانفاس", "tense", "gripping", "thrilling"),
    "strong_opening": _n("بدايه قويه", "يبدا مباشره", "من اول دقيقه", "strong opening", "starts immediately"),
    "pursuit": _n("مطارده", "مطاردات", "chase", "pursuit"),
    "rescue": _n("انقاذ", "rescue"),
    "heist": _n("سرقه", "heist"),
    "revenge": _n("انتقام", "revenge"),
    "survival": _n("نجاه", "survival"),
}

INHERENT_NEGATIVE: dict[str, list[str]] = {
    "slow_pacing": _n("بطيء", "بطيئ", "بطي", "slow", "sluggish"),
    "boring": _n("ممل", "مملل", "مللت", "طفش", "طفشت", "boring", "bored", "dull"),
    "excessive_dialogue": _n(
        "حوار كثير", "كلام كثير", "سوالف كثير", "حوارات", "too much dialogue", "talky", "too much talking"
    ),
    "chaotic_camera": _n("مهزوز", "مهزوزه", "الكاميرا تهتز", "shaky", "shaky cam", "chaotic editing"),
    "low_energy": _n("ميت", "ميته", "بارد", "dead", "lifeless", "flat"),
    "confusing_story": _n("معقد", "مشوش", "ما فهمت", "مو مفهوم", "confusing", "convoluted"),
    "irrational_plotting": _n("غبي", "سخيف", "غير منطقي", "مو منطقي", "stupid", "illogical", "dumb"),
    "weak_tension": _n(
        "ما حبس انفاسي", "ما خطف انفاسي", "ماخذ انفاسي", "didn't take my breath", "no tension"
    ),
    "generic_high_concept": _n("مكرر", "عادي جدا", "generic", "predictable"),
    "low_production": _n("رخيص", "ضعيف الانتاج", "انتاج ضعيف", "cheap", "low budget"),
    "weak_cast": _n("الممثلين ضعاف", "تمثيل ضعيف", "التمثيل ضعيف", "bad acting", "weak acting"),
}

OPENING_MARKERS = _n(
    "اول", "البدايه", "البداية", "دقايق", "دقائق", "first", "opening", "minutes", "beginning"
)
CONTRAST_MARKERS = _n("لكن", "بس", "الا ان", "مع ان", "but", "however", "although", "though")

# Expansion for compound statements (section 21: "لا اريد شي ميت")
DEAD_EXPANSION = ["low_energy", "low_production", "weak_cast", "indie_feeling"]
