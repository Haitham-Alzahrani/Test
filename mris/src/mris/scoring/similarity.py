"""Reference similarity on multi-characteristic trait vectors (not genre matching).

A candidate counts as similar to a reference only when at least ``MIN_SHARED`` characteristics
align (e.g. "crime thriller" alone never makes something similar to The Town).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mris.scoring.assessment import Assessment

MIN_SHARED = 3

# Style / quality traits derived from assessment values (threshold on the 0..1 scores)
_DERIVED = {
    "strong_opening": ("opening_score", 0.68),
    "fast_pacing": ("pacing", 0.68),
    "continuous_events": ("event_continuity", 0.65),
    "strong_tension": ("tension_continuity", 0.68),
    "strong_acting": ("acting_quality", 0.68),
    "strong_story": ("plot_coherence", 0.66),
    "clear_story": ("story_clarity", 0.66),
    "event_progression": ("story_progression", 0.66),
    "strong_production": ("production_quality", 0.68),
    "clear_action": ("camera_stability", 0.66),
    "realistic": ("realism", 0.62),
    "entertaining": ("action_quality", 0.68),
}
_DERIVED_NEGATIVE = {
    "slow_opening": ("opening_score", 0.4),
    "slow_pacing": ("pacing", 0.4),
    "excessive_dialogue": ("dialogue_to_event_ratio", 0.4),
    "weak_tension": ("tension_continuity", 0.4),
    "chaotic_camera": ("camera_stability", 0.4),
}


def candidate_traits(a: Assessment, modern: bool = True) -> dict[str, float]:
    traits: dict[str, float] = dict(a.themes)
    for trait, (key, threshold) in _DERIVED.items():
        v = a.get(key)
        if v is not None and v >= threshold:
            traits[trait] = round(v, 3)
    for trait, (key, threshold) in _DERIVED_NEGATIVE.items():
        v = a.get(key)
        if v is not None and v <= threshold:
            traits[trait] = round(1 - v, 3)
    for flag in (
        "slow_opening",
        "excessive_dialogue",
        "chaotic_camera",
        "low_production",
        "generic_high_concept",
    ):
        if flag in a.flags:
            traits[flag] = 1.0 if a.flags[flag] == "strong" else 0.6
    if "low_production" in a.flags:
        traits["low_energy"] = traits["low_production"]
    if "immediate_danger" not in traits and (a.get("opening_score") or 0) >= 0.75:
        traits["immediate_danger"] = 0.7
    if modern:
        traits["modern_setting"] = 1.0
    if a.franchise_dependency == "none":
        traits["standalone"] = 1.0
    if "crime" in traits or "heist" in traits:
        traits.setdefault("action", 0.7)
    return traits


@dataclass
class ReferenceMatch:
    title: str
    similarity: float
    shared: list[str] = field(default_factory=list)
    importance: float = 1.0


def weighted_jaccard(
    a: dict[str, float], b: dict[str, float], weights: dict[str, float]
) -> tuple[float, list[str]]:
    keys = set(a) | set(b)
    if not keys:
        return 0.0, []
    num = den = 0.0
    shared = []
    for k in keys:
        w = weights.get(k, 1.0)
        x, y = a.get(k, 0.0), b.get(k, 0.0)
        num += w * min(x, y)
        den += w * max(x, y)
        if x >= 0.5 and y >= 0.5:
            shared.append(k)
    return (num / den if den else 0.0), sorted(shared)


def trait_weights(affinities: dict[str, float]) -> dict[str, float]:
    """Traits the user cares about (positively or negatively) weigh more in the comparison."""
    return {k: max(0.3, min(2.0, 1.0 + abs(v))) for k, v in affinities.items()}


def compare(
    traits: dict[str, float],
    references: list[tuple[str, dict[str, float], float]],
    affinities: dict[str, float],
) -> list[ReferenceMatch]:
    """references: (title, trait vector, importance weight). Returns matches sorted by strength."""
    weights = trait_weights(affinities)
    out = []
    for title, ref_traits, importance in references:
        if not ref_traits:
            continue
        sim, shared = weighted_jaccard(traits, ref_traits, weights)
        if len(shared) >= MIN_SHARED:
            out.append(ReferenceMatch(title, round(sim, 3), shared, importance))
    return sorted(out, key=lambda m: m.similarity * m.importance, reverse=True)


def affinity_score(traits: dict[str, float], affinities: dict[str, float]) -> float | None:
    """0..1 summary of how the candidate's traits line up with learned likes/dislikes."""
    relevant = [(affinities[t], v) for t, v in traits.items() if t in affinities]
    if not relevant:
        return None
    raw = sum(a * v for a, v in relevant) / max(1.0, sum(abs(a) for a, _ in relevant))
    return round(0.5 + 0.5 * max(-1.0, min(1.0, raw)), 3)


def reference_dimension(
    positive: list[ReferenceMatch], negative: list[ReferenceMatch], affinity: float | None
) -> float | None:
    if not positive and affinity is None:
        return None
    best = 0.0
    if positive:
        top = positive[:2]
        best = sum(m.similarity * m.importance for m in top) / len(top)
        best = min(1.0, best * 1.6)  # jaccard over sparse vectors rarely exceeds ~0.6
    if negative:
        best = max(0.0, best - 0.5 * negative[0].similarity)
    if affinity is None:
        return round(best, 3)
    return round(0.6 * best + 0.4 * affinity, 3) if positive else round(affinity, 3)
