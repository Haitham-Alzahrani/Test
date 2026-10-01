"""Controlled vocabularies stored in the database as plain strings."""

from __future__ import annotations

from enum import StrEnum


class RatingLabel(StrEnum):
    LOVED = "loved"
    EXCELLENT = "excellent"
    LIKED = "liked"
    GOOD = "good"
    MEDIUM = "medium"
    AVERAGE = "average"
    MEDIUM_LOW = "medium_low"
    DISLIKED = "disliked"

    @property
    def polarity(self) -> int:
        """+1 positive, 0 neutral/medium, -1 negative."""
        if self in (RatingLabel.LOVED, RatingLabel.EXCELLENT, RatingLabel.LIKED, RatingLabel.GOOD):
            return 1
        if self in (RatingLabel.MEDIUM, RatingLabel.AVERAGE, RatingLabel.MEDIUM_LOW):
            return 0
        return -1

    @property
    def is_medium(self) -> bool:
        return self.polarity == 0


class Importance(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def weight(self) -> float:
        return {"very_high": 1.0, "high": 0.8, "medium": 0.55, "low": 0.3}[self.value]


class WatchStatus(StrEnum):
    WATCHED = "watched"
    PARTIALLY_WATCHED = "partially_watched"
    NOT_WATCHED = "not_watched"


class WatchlistStatus(StrEnum):
    WATCH_LATER = "watch_later"
    WATCHED = "watched"
    REMOVED = "removed"


class ResearchStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"  # strong, HIGH confidence, eligible for display
    REJECTED = "rejected"  # hard exclusion or low compatibility
    BLOCKED = "blocked"  # watched / rejected before / watchlist / declined ...
    BORDERLINE = "borderline"  # compatible-looking but score below pass threshold
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # not enough real evidence to decide
    ERROR = "error"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SourceType(StrEnum):
    METADATA = "metadata"
    RATINGS = "ratings"
    PROFESSIONAL = "professional"
    AUDIENCE = "audience"
    TRAILER = "trailer"
    MANUAL = "manual"
    OTHER = "other"


class UserResponse(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    WATCHED = "watched"
    WATCH_LATER = "watch_later"
    DECLINED = "declined"


class RuleType(StrEnum):
    WEIGHT = "weight"  # positive score weights (sum to 100)
    PENALTY = "penalty"  # hard penalties (points subtracted)
    EXCLUSION = "exclusion"  # automatic reject switches
    TRAIT_AFFINITY = "trait_affinity"  # learned like/dislike of traits (-1..1)
    THRESHOLD = "threshold"


RELEASE_CATEGORY_ORDER = {"theatrical": 0, "streaming": 1, "wide": 2, "independent": 3, "unknown": 4}
