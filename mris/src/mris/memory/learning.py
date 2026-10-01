"""Feedback loop: store what the user said and adjust the taste model.

Every adjustment is small, bounded and logged in the returned report so learning stays
transparent and reversible (preference rules can be edited with `mris profile`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mris.models import Movie, RatingLabel, RuleType, User
from mris.repositories import Repos
from mris.scoring.defaults import DEFAULT_PENALTIES, DEFAULT_WEIGHTS, TRAIT_TO_DIMENSION, TRAIT_TO_PENALTY

AFFINITY_STEP = {"loved": 0.10, "excellent": 0.10, "liked": 0.05, "good": 0.04}
WEIGHT_STEP = 0.5
PENALTY_STEP = {"disliked": 2.0, "medium": 1.0, "medium_low": 1.0, "average": 1.0}
IMPORTANCE_FOR = {"loved": "high", "excellent": "high"}  # only top ratings become taste references


@dataclass
class LearningReport:
    movie: str
    changes: list[str] = field(default_factory=list)

    def add(self, text: str) -> None:
        self.changes.append(text)


def _rating(label: str) -> RatingLabel:
    try:
        return RatingLabel(label)
    except ValueError as exc:
        raise ValueError(
            f"Unknown rating label '{label}'. Use one of: {[r.value for r in RatingLabel]}"
        ) from exc


def record_feedback(
    repos: Repos,
    user: User,
    movie: Movie,
    rating_label: str,
    positive_traits: list[str] | None = None,
    negative_traits: list[str] | None = None,
    notes: str | None = None,
    rating_value: float | None = None,
    status: str = "watched",
    importance: str | None = None,
    learn: bool = True,
) -> LearningReport:
    rating = _rating(rating_label)
    pos = list(dict.fromkeys(positive_traits or []))
    neg = list(dict.fromkeys(negative_traits or []))
    report = LearningReport(movie.label)
    importance = importance or (
        "very_high" if rating.polarity < 0 and neg else "high" if neg or pos else "medium"
    )

    repos.feedback.add(
        user,
        movie,
        rating.value,
        status=status,
        rating_value=rating_value,
        reason_text=notes,
        positive_traits=pos,
        negative_traits=neg,
        importance_for_learning=importance,
    )
    report.add(f"feedback stored: {rating.value} ({status})")

    if status == "watched":
        if repos.watchlist.set_status(user, movie, "watched"):
            report.add("removed from watch-later (now watched)")
    response = "watched" if rating.polarity >= 0 else "declined"
    repos.recommendations.respond(user, movie, response)

    user_traits = {t: 1.0 for t in pos}
    user_traits.update({t: 1.0 for t in neg})
    if user_traits:
        repos.movies.set_traits(movie, user_traits, source="user")

    if rating.polarity > 0 and rating.value in IMPORTANCE_FOR:
        repos.references.upsert(user, movie, rating.value, IMPORTANCE_FOR[rating.value], notes=notes)
        report.add("added/updated as a positive reference movie")
    elif rating.polarity <= 0:
        repos.references.remove(user, movie)

    if learn:
        _learn(repos, user, movie, rating, pos, neg, report)
    return report


def _learn(
    repos: Repos,
    user: User,
    movie: Movie,
    rating: RatingLabel,
    pos: list[str],
    neg: list[str],
    report: LearningReport,
) -> None:
    prefs = repos.preferences
    movie_traits = repos.movies.traits(movie.id)
    if rating.polarity > 0:
        step = AFFINITY_STEP.get(rating.value, 0.04)
        for t in pos:
            prefs.adjust(user, RuleType.TRAIT_AFFINITY, t, step, -1.0, 1.0, notes=f"from {movie.label}")
            dim = TRAIT_TO_DIMENSION.get(t)
            if dim:
                prefs.adjust(user, RuleType.WEIGHT, dim, WEIGHT_STEP, 3.0, 30.0, notes=f"from {movie.label}")
        if pos:
            report.add("increased weight of: " + ", ".join(pos))
        shared = [t for t, v in movie_traits.items() if v >= 0.6 and t not in pos and t not in neg]
        for t in shared:
            prefs.adjust(
                user, RuleType.TRAIT_AFFINITY, t, step / 3, -1.0, 1.0, notes=f"shared by {movie.label}"
            )
        if shared:
            report.add(
                "slightly increased affinity for traits of this movie: " + ", ".join(sorted(shared)[:8])
            )
        for t in neg:  # liked overall but with a named weakness (e.g. The Night Manager: too much dialogue)
            _penalize(prefs, user, t, 1.0, movie, report)
    elif rating.is_medium:
        decreased = [t for t, v in movie_traits.items() if v >= 0.6 and t not in neg]
        for t in decreased:
            prefs.adjust(user, RuleType.TRAIT_AFFINITY, t, -0.03, -1.0, 1.0, notes=f"medium: {movie.label}")
        if decreased:
            report.add("lowered confidence in this pattern: " + ", ".join(sorted(decreased)[:8]))
        for t in neg:
            _penalize(prefs, user, t, PENALTY_STEP[rating.value], movie, report)
    else:
        for t in neg:
            _penalize(prefs, user, t, PENALTY_STEP["disliked"], movie, report)
            prefs.adjust(user, RuleType.TRAIT_AFFINITY, t, -0.1, -1.0, 1.0, notes=f"disliked: {movie.label}")
        others = [t for t, v in movie_traits.items() if v >= 0.6 and t not in neg]
        for t in others:
            prefs.adjust(user, RuleType.TRAIT_AFFINITY, t, -0.02, -1.0, 1.0, notes=f"disliked: {movie.label}")


def _penalize(prefs, user: User, trait: str, step: float, movie: Movie, report: LearningReport) -> None:
    key = TRAIT_TO_PENALTY.get(trait)
    if not key:
        return
    current = prefs.get(user, RuleType.PENALTY, key)
    if current is None:
        prefs.set(user, RuleType.PENALTY, key, DEFAULT_PENALTIES.get(key, 10.0), source="seed")
    prefs.adjust(user, RuleType.PENALTY, key, step, 0.0, 35.0, notes=f"from {movie.label}")
    report.add(f"increased penalty '{key}' (+{step:g})")


def record_preference_statement(
    repos: Repos, user: User, positive: list[str], negative: list[str], text: str
) -> LearningReport:
    """General taste statements such as "لا اريد شي ميت"."""
    report = LearningReport("profile")
    for t in negative:
        repos.preferences.adjust(
            user, RuleType.TRAIT_AFFINITY, t, -0.15, -1.0, 1.0, source="user", notes=text
        )
        key = TRAIT_TO_PENALTY.get(t)
        if key:
            current = repos.preferences.get(user, RuleType.PENALTY, key)
            base = current.value if current else DEFAULT_PENALTIES.get(key, 10.0)
            repos.preferences.set(
                user, RuleType.PENALTY, key, min(35.0, base + 2.0), source="user", notes=text
            )
    for t in positive:
        repos.preferences.adjust(user, RuleType.TRAIT_AFFINITY, t, 0.15, -1.0, 1.0, source="user", notes=text)
    if negative:
        report.add("avoid: " + ", ".join(negative))
    if positive:
        report.add("prefer: " + ", ".join(positive))
    return report


def record_cast_rejection(
    repos: Repos, user: User, movie: Movie, universal: bool = False, note: str | None = None
) -> LearningReport:
    """'لا يعجبني الممثلين' - a cast-related negative for THIS movie (not a universal actor ban
    unless the user says so explicitly)."""
    report = LearningReport(movie.label)
    leads = [c["name"] for c in sorted(movie.cast or [], key=lambda c: c.get("order", 99))[:2]]
    for name in leads:
        repos.actors.add(
            user,
            name,
            -1.0,
            scope="universal" if universal else "movie",
            movie=movie,
            reason=note or "user did not like the actors",
        )
    if leads:
        report.add(("universal" if universal else "movie-specific") + " cast dislike: " + ", ".join(leads))
    repos.rejected.add(user, movie, note or "user did not like the cast (trailer/cast)", "user_cast", "HIGH")
    repos.recommendations.respond(user, movie, "declined")
    report.add("movie moved to rejected list (cast)")
    return report


def ensure_default_rules(repos: Repos, user: User) -> None:
    from mris.scoring.defaults import (
        DEFAULT_EXCLUSIONS,
        DEFAULT_THRESHOLDS,
        DEFAULT_TRAIT_AFFINITIES,
    )

    for key, value in DEFAULT_WEIGHTS.items():
        repos.preferences.ensure(user, RuleType.WEIGHT, key, value)
    for key, value in DEFAULT_PENALTIES.items():
        repos.preferences.ensure(user, RuleType.PENALTY, key, value)
    for key, label in DEFAULT_EXCLUSIONS.items():
        repos.preferences.ensure(user, RuleType.EXCLUSION, key, 1.0, notes=label)
    for key, value in DEFAULT_THRESHOLDS.items():
        repos.preferences.ensure(user, RuleType.THRESHOLD, key, value)
    for key, (value, note) in DEFAULT_TRAIT_AFFINITIES.items():
        repos.preferences.ensure(user, RuleType.TRAIT_AFFINITY, key, value, notes=note)
