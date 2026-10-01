"""Turn verified metadata + aggregated evidence into the explicit assessment fields
(opening model, story progression model, acting model, production model, realism model)
and into risk flags with a severity.

Rule of the module: a field without evidence stays ``None``.  Genre or rating never stands in
for opening quality.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from mris.research.evidence import EvidenceSummary, detect_themes
from mris.search.base import MovieMetadata, Ratings

STRONG, MODERATE = "strong", "moderate"


def _avg(*values: float | None) -> float | None:
    known = [v for v in values if v is not None]
    return round(mean(known), 3) if known else None


@dataclass
class Assessment:
    values: dict[str, float | None] = field(default_factory=dict)
    opening_confidence: str | None = None
    opening_evidence: list[dict[str, Any]] = field(default_factory=list)
    opening_event_start_minutes: float | None = None
    slow_burn: bool = False
    franchise_dependency: str | None = None
    flags: dict[str, str] = field(default_factory=dict)  # flag -> strong | moderate
    flag_reasons: dict[str, str] = field(default_factory=dict)
    themes: dict[str, float] = field(default_factory=dict)
    evidence_domains: int = 0
    professional_domains: int = 0
    audience_domains: int = 0

    def get(self, key: str) -> float | None:
        return self.values.get(key)

    def raise_flag(self, flag: str, severity: str, reason: str) -> None:
        if self.flags.get(flag) == STRONG:
            return
        self.flags[flag] = severity
        self.flag_reasons[flag] = reason


def cast_recognizability(meta: MovieMetadata) -> float | None:
    """Recognisability of the top-billed cast from TMDb popularity (not a quality judgement)."""
    pops = [c.popularity for c in sorted(meta.cast, key=lambda c: c.order)[:3] if c.popularity is not None]
    if not pops:
        return None
    top = max(pops)
    avg = mean(pops)
    value = 0.6 * top + 0.4 * avg
    lo, hi = math.log1p(1.5), math.log1p(25)
    return round(max(0.0, min(1.0, (math.log1p(value) - lo) / (hi - lo))), 3)


def budget_signal(budget: int | None) -> float | None:
    if not budget:
        return None
    for floor, score in ((60_000_000, 0.9), (25_000_000, 0.78), (10_000_000, 0.62), (3_000_000, 0.45)):
        if budget >= floor:
            return score
    return 0.25


def assess(
    meta: MovieMetadata,
    summary: EvidenceSummary,
    ratings: Ratings | None = None,
    known_dependency: str | None = None,
    max_opening_minutes: float = 15.0,
) -> Assessment:
    a = Assessment()
    s = summary.score

    # ---- Opening quality model -------------------------------------------------------------
    opening = summary.get("opening")
    minutes = summary.median_opening_minutes
    opening_score = opening.score()
    if minutes is not None:
        if minutes > max_opening_minutes:
            opening_score = min(opening_score if opening_score is not None else 0.5, 0.25)
        elif minutes <= 10 and opening_score is None:
            opening_score = 0.72
    opening_domains = opening.domains | {d for _, d in summary.opening_minutes}
    n = len(opening_domains)
    has_pro = bool(opening_domains & summary.professional_domains)
    if n == 0:
        conf = None
    elif n >= 3 or (n >= 2 and has_pro):
        conf = "HIGH"
    elif n >= 2 or has_pro:
        conf = "MEDIUM"
    else:
        conf = "LOW"
    contradictory = len(opening.pos_domains) >= 2 and len(opening.neg_domains) >= 2
    if contradictory and conf:
        conf = {"HIGH": "MEDIUM", "MEDIUM": "LOW", "LOW": "LOW"}[conf]
    a.opening_confidence = conf
    a.opening_evidence = opening.examples + [
        {"domain": d, "minutes": v, "polarity": 0, "quote": f"opening event start ≈ {v:.0f} min"}
        for v, d in summary.opening_minutes[:3]
    ]
    a.opening_event_start_minutes = minutes

    # ---- Story progression / pacing models ---------------------------------------------------
    plot_coherence = s("plot_coherence")
    a.values = {
        "opening_score": round(opening_score, 3) if opening_score is not None else None,
        "pacing": s("pacing"),
        "story_clarity": s("story_clarity"),
        "story_progression": s("story_progression"),
        "event_continuity": s("event_continuity"),
        "plot_coherence": plot_coherence,
        "dialogue_to_event_ratio": s("dialogue"),
        "tension_continuity": s("tension_continuity"),
        "action_quality": s("action_quality"),
        "acting_quality": s("acting_quality"),
        "character_credibility": s("character_credibility"),
        "cinematography_quality": s("cinematography_quality"),
        "camera_stability": s("camera_stability"),
        "realism": s("realism"),
        "internal_logic": plot_coherence,
    }
    a.values["action_clarity"] = a.values["camera_stability"]
    a.values["visual_quality"] = a.values["cinematography_quality"]

    # Cast: recognisability (metadata) blended with what reviewers say about the cast.
    a.values["cast_strength"] = _avg(cast_recognizability(meta), s("cast_strength"))

    # Production: budget (metadata) blended with review evidence; evidence weighs more.
    ev_prod = _avg(s("production_quality"), s("cinematography_quality"))
    bud = budget_signal(meta.budget)
    if ev_prod is not None and bud is not None:
        a.values["production_quality"] = round(0.65 * ev_prod + 0.35 * bud, 3)
    else:
        a.values["production_quality"] = ev_prod if ev_prod is not None else bud

    realism = summary.get("realism")
    a.values["exaggeration_level"] = round(realism.neg / realism.total, 3) if realism.total else None
    for k, v in list(a.values.items()):
        if v is not None:
            a.values[k] = round(v, 3)

    # ---- Franchise dependency -------------------------------------------------------------
    fr = summary.get("franchise")
    is_sequel = bool(meta.collection_position and meta.collection_position > 1)
    standalone_praised = len(fr.pos_domains) >= 1 and fr.pos >= fr.neg
    if known_dependency:
        a.franchise_dependency = known_dependency
    elif is_sequel:
        a.franchise_dependency = "partial" if standalone_praised else "strong"
    elif len(fr.neg_domains) >= 2 and fr.neg > fr.pos:
        a.franchise_dependency = "strong"
    elif fr.neg_domains and fr.neg > fr.pos:
        a.franchise_dependency = "partial"
    elif meta.tmdb_id is not None:
        a.franchise_dependency = "none"  # verified: TMDb lists no collection and reviews raise none

    # ---- Themes (for reference similarity) ------------------------------------------------
    corpus = " ".join([meta.overview or "", " ".join(meta.keywords)])
    themes = detect_themes(corpus)
    a.themes = {k: min(1.0, 0.6 + 0.2 * c) for k, c in themes.items()}

    a.evidence_domains = len(summary.domains)
    a.professional_domains = len(summary.professional_domains)
    a.audience_domains = len(summary.audience_domains)

    _raise_flags(a, meta, summary, ratings, max_opening_minutes)
    return a


def _raise_flags(
    a: Assessment,
    meta: MovieMetadata,
    summary: EvidenceSummary,
    ratings: Ratings | None,
    max_minutes: float,
) -> None:
    opening = summary.get("opening")
    op = a.get("opening_score")
    minutes = a.opening_event_start_minutes
    if minutes is not None and minutes > max_minutes and (op is None or op < 0.5):
        a.raise_flag("slow_opening", STRONG, f"reviews put the main event at ~{minutes:.0f} minutes")
    if op is not None and op < 0.4 and len(opening.neg_domains) >= 2:
        a.raise_flag(
            "slow_opening", STRONG, f"{len(opening.neg_domains)} sources describe a slow/long opening"
        )
    elif op is not None and op < 0.45 and opening.neg_domains:
        a.raise_flag("slow_opening", MODERATE, "a source describes a slow opening")

    burn = summary.flag_domains("slow_burn")
    if len(burn) >= 2:
        a.slow_burn = True
        a.raise_flag("slow_burn", STRONG, f"described as a slow-burn by {len(burn)} sources")
    elif burn:
        a.slow_burn = True
        a.raise_flag("slow_burn", MODERATE, "described as a slow-burn by one source")

    dlg = summary.get("dialogue")
    dlg_domains = dlg.neg_domains | summary.flag_domains("excessive_dialogue")
    dlg_score = a.get("dialogue_to_event_ratio")
    if len(dlg_domains) >= 2 and (dlg_score is None or dlg_score < 0.4):
        a.raise_flag("excessive_dialogue", STRONG, "several sources call it talky / dialogue-heavy")
    elif dlg_domains and (dlg_score is None or dlg_score < 0.5):
        a.raise_flag("excessive_dialogue", MODERATE, "one source calls it talky")

    clar = summary.get("story_clarity")
    clar_score = a.get("story_clarity")
    if clar_score is not None and clar_score < 0.4 and len(clar.neg_domains) >= 2:
        a.raise_flag("confusing_story", STRONG, "several sources call the story confusing")
    elif clar_score is not None and clar_score < 0.45 and clar.neg_domains:
        a.raise_flag("confusing_story", MODERATE, "a source calls the story confusing")

    for flag, pretty in (
        ("chaotic_camera", "shaky / chaotic camera or editing"),
        ("irrational_plotting", "illogical plotting / characters"),
        ("low_production", "cheap / small-feeling production"),
    ):
        doms = summary.flag_domains(flag)
        if len(doms) >= 2:
            a.raise_flag(flag, STRONG, f"{pretty} ({len(doms)} sources)")
        elif doms:
            a.raise_flag(flag, MODERATE, f"{pretty} (1 source)")

    if len(summary.flag_domains("generic_high_concept")) >= 2:
        a.raise_flag("generic_high_concept", MODERATE, "described as generic / predictable")

    if meta.budget and meta.budget < 5_000_000 and (a.get("production_quality") or 0) < 0.5:
        a.raise_flag("low_production", STRONG, "very low budget and no evidence of strong production")

    acting = summary.get("acting_quality")
    act = a.get("acting_quality")
    if act is not None and act < 0.4 and len(acting.neg_domains) >= 2:
        a.raise_flag("weak_cast", STRONG, "several sources criticise the acting")
    elif act is not None and act < 0.45 and acting.neg_domains:
        a.raise_flag("weak_cast", MODERATE, "a source criticises the acting")
    rec = cast_recognizability(meta)
    if rec is not None and rec < 0.15:
        a.raise_flag("weak_cast", MODERATE, "little-known lead cast (potential cast mismatch)")

    if a.franchise_dependency == "strong":
        a.raise_flag("franchise_dependency", STRONG, "depends on previous films / a franchise")
    elif a.franchise_dependency == "partial":
        a.raise_flag("franchise_dependency", MODERATE, "part of a franchise but reportedly works standalone")

    if meta.original_language and meta.original_language != "en":
        a.raise_flag("non_english", MODERATE, f"primary language '{meta.original_language}'")

    weak = []
    if ratings and ratings.imdb is not None and (ratings.imdb_votes or 0) >= 1000 and ratings.imdb < 5.8:
        weak.append(f"IMDb {ratings.imdb}")
    if (
        meta.vote_average is not None
        and (meta.vote_count or 0) >= 150
        and meta.vote_average < 5.8
        and not (ratings and ratings.imdb is not None)
    ):
        weak.append(f"TMDb {meta.vote_average:.1f}")
    if weak:
        a.raise_flag("weak_ratings", MODERATE, "low audience ratings: " + ", ".join(weak))
