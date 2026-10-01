"""Hard exclusions (automatic rejects). Every rule can be switched off in `preference_rules`
(rule_type = exclusion) - e.g. if the user later decides sci-fi is acceptable."""

from __future__ import annotations

from dataclasses import dataclass

from mris.research.lexicon import (
    COMPILED_EXCLUSION_TEXT,
    EXCLUDED_COUNTRIES,
    EXCLUDED_LANGUAGES,
    EXCLUSION_GENRES,
    PRE_2000_SETTING,
)
from mris.scoring.assessment import STRONG, Assessment
from mris.search.base import MovieMetadata
from mris.text import normalize_text


@dataclass
class Exclusion:
    key: str
    reason: str


def find_exclusions(
    meta: MovieMetadata,
    assessment: Assessment | None,
    enabled: set[str],
    rejected_franchises: set[str] | None = None,
) -> list[Exclusion]:
    out: list[Exclusion] = []

    def add(key: str, reason: str) -> None:
        if key in enabled and all(e.key != key for e in out):
            out.append(Exclusion(key, reason))

    genres = set(meta.genres)
    corpus = " . ".join([meta.overview or "", " . ".join(meta.keywords)])

    for genre, key in EXCLUSION_GENRES.items():
        if genre in genres and key != "historical_setting":
            add(key, f"genre: {genre}")

    for key, pattern in COMPILED_EXCLUSION_TEXT.items():
        hits = {m.group(0).lower() for m in pattern.finditer(corpus)}
        if not hits:
            continue
        if key == "historical_setting" and "History" not in genres and len(hits) < 2:
            # a single word like "biopic" in the keywords is not enough without the genre
            continue
        add(key, f"{key.replace('_', ' ')}: {', '.join(sorted(hits)[:3])}")

    for m in PRE_2000_SETTING.finditer(corpus):
        year = int(m.group(1) or m.group(2))
        if year < 2000:
            add("pre_2000_setting", f"story set in {year}s" if m.group(2) else f"story set in {year}")
            break

    if "History" in genres and any(e.key in ("pre_2000_setting", "historical_setting") for e in out):
        add("historical_setting", "genre: History with a period setting")

    lang = (meta.original_language or "").lower()
    if lang in EXCLUDED_LANGUAGES:
        add("excluded_language", f"primary language: {EXCLUDED_LANGUAGES[lang]}")
    elif lang and lang != "en" and set(meta.countries) & EXCLUDED_COUNTRIES:
        add(
            "excluded_language",
            f"Asian production ({', '.join(sorted(set(meta.countries) & EXCLUDED_COUNTRIES))})",
        )

    if assessment is not None:
        if assessment.franchise_dependency == "strong":
            add(
                "franchise_required",
                assessment.flag_reasons.get("franchise_dependency", "franchise dependency"),
            )
        if assessment.flags.get("slow_burn") == STRONG:
            add("slow_burn", assessment.flag_reasons["slow_burn"])
        if assessment.flags.get("slow_opening") == STRONG:
            add("weak_opening", assessment.flag_reasons["slow_opening"])
        if assessment.flags.get("excessive_dialogue") == STRONG and (assessment.get("pacing") or 0.5) < 0.5:
            add("dialogue_dominated", assessment.flag_reasons["excessive_dialogue"])

    if rejected_franchises and meta.collection_name:
        if normalize_text(meta.collection_name.replace("Collection", "")) in rejected_franchises or (
            normalize_text(meta.collection_name) in rejected_franchises
        ):
            add("rejected_franchise", f"belongs to rejected franchise: {meta.collection_name}")
    return out
