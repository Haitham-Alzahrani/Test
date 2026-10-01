"""Transparent 0-100 compatibility score, confidence level and the final research decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from mris.models.enums import Confidence, ResearchStatus
from mris.scoring.assessment import STRONG, Assessment
from mris.scoring.defaults import DEFAULT_PENALTIES, DEFAULT_WEIGHTS

NEUTRAL = 0.5  # value used for unknown dimensions (they also lower confidence)

# Penalties applied at half strength for moderate evidence
_FLAG_TO_PENALTY = {
    "slow_opening": "slow_opening",
    "slow_burn": "slow_opening",
    "excessive_dialogue": "excessive_dialogue",
    "confusing_story": "confusing_story",
    "weak_cast": "weak_cast",
    "franchise_dependency": "franchise_dependency",
    "chaotic_camera": "chaotic_camera",
    "low_production": "low_production",
    "irrational_plotting": "irrational_plotting",
    "generic_high_concept": "generic_high_concept",
    "non_english": "non_english",
    "weak_ratings": "weak_ratings",
    "potential_cast_mismatch": "potential_cast_mismatch",
    "negative_reference_similarity": "negative_reference_similarity",
}


def dimension_values(a: Assessment, reference_similarity: float | None) -> dict[str, float | None]:
    def avg(*keys: str) -> float | None:
        vals = [a.get(k) for k in keys if a.get(k) is not None]
        return round(mean(vals), 3) if vals else None

    return {
        "opening": a.get("opening_score"),
        "story_quality": avg("story_clarity", "plot_coherence", "character_credibility"),
        "story_progression": avg("story_progression", "event_continuity"),
        "acting_cast": avg("acting_quality", "character_credibility", "cast_strength"),
        "pacing_continuity": avg("pacing", "event_continuity", "dialogue_to_event_ratio"),
        "production": avg("production_quality", "cinematography_quality", "camera_stability"),
        "tension_action": avg("tension_continuity", "action_quality"),
        "reference_similarity": reference_similarity,
    }


@dataclass
class ScoreResult:
    total: float
    dimensions: dict[str, float | None]
    contributions: dict[str, float]
    penalties: dict[str, float]
    known_dimensions: int
    confidence: Confidence
    confidence_reasons: list[str] = field(default_factory=list)

    def breakdown(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "dimensions": self.dimensions,
            "contributions": self.contributions,
            "penalties": self.penalties,
            "known_dimensions": self.known_dimensions,
            "confidence": self.confidence.value,
            "confidence_reasons": self.confidence_reasons,
        }


def compute_score(
    a: Assessment,
    reference_similarity: float | None,
    metadata_verified: bool,
    weights: dict[str, float] | None = None,
    penalties: dict[str, float] | None = None,
    extra_flags: dict[str, str] | None = None,
) -> ScoreResult:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    penalties = {**DEFAULT_PENALTIES, **(penalties or {})}
    total_w = sum(weights.get(k, 0) for k in DEFAULT_WEIGHTS) or 1.0
    dims = dimension_values(a, reference_similarity)

    contributions = {}
    for key, value in dims.items():
        w = weights.get(key, 0) * 100.0 / total_w
        contributions[key] = round(w * (value if value is not None else NEUTRAL), 2)

    applied: dict[str, float] = {}
    flags = {**a.flags, **(extra_flags or {})}
    for flag, severity in flags.items():
        pkey = _FLAG_TO_PENALTY.get(flag)
        if not pkey:
            continue
        amount = penalties.get(pkey, 0.0) * (1.0 if severity == STRONG else 0.5)
        applied[pkey] = max(applied.get(pkey, 0.0), round(amount, 2))  # slow_burn & slow_opening don't stack

    total = round(max(0.0, min(100.0, sum(contributions.values()) - sum(applied.values()))), 1)
    known = sum(1 for k, v in dims.items() if v is not None and k != "reference_similarity")
    conf, reasons = _confidence(a, metadata_verified, known)
    return ScoreResult(total, dims, contributions, applied, known, conf, reasons)


def _confidence(a: Assessment, metadata_verified: bool, known: int) -> tuple[Confidence, list[str]]:
    reasons = []
    if not metadata_verified:
        reasons.append("core metadata not verified")
    if a.opening_confidence is None:
        reasons.append("no evidence about the opening")
    elif a.opening_confidence == "LOW":
        reasons.append("opening evidence from a single non-professional source")
    if known < 5:
        reasons.append(f"only {known}/7 quality dimensions have evidence")
    if a.evidence_domains < 3:
        reasons.append(f"only {a.evidence_domains} independent sources")
    if a.professional_domains < 1:
        reasons.append("no professional review")

    if (
        metadata_verified
        and a.opening_confidence in ("HIGH", "MEDIUM")
        and known >= 5
        and a.evidence_domains >= 3
        and a.professional_domains >= 1
    ):
        return Confidence.HIGH, reasons
    if metadata_verified and a.opening_confidence is not None and known >= 3 and a.evidence_domains >= 2:
        return Confidence.MEDIUM, reasons
    return Confidence.LOW, reasons


def decide(
    score: ScoreResult,
    exclusion_reasons: list[str],
    pass_threshold: float,
    reject_threshold: float,
) -> tuple[ResearchStatus, str]:
    if exclusion_reasons:
        return ResearchStatus.REJECTED, "hard exclusion: " + "; ".join(exclusion_reasons)
    if score.total < reject_threshold and score.confidence != Confidence.LOW and score.known_dimensions >= 4:
        return ResearchStatus.REJECTED, f"low compatibility ({score.total:.0f} < {reject_threshold:.0f})"
    if score.confidence == Confidence.HIGH and score.total >= pass_threshold:
        return ResearchStatus.PASSED, f"compatibility {score.total:.0f} with HIGH confidence"
    if score.confidence != Confidence.HIGH:
        return (
            ResearchStatus.INSUFFICIENT_EVIDENCE,
            f"confidence {score.confidence.value}: " + "; ".join(score.confidence_reasons),
        )
    return (
        ResearchStatus.BORDERLINE,
        f"compatibility {score.total:.0f} below pass threshold {pass_threshold:.0f}",
    )
