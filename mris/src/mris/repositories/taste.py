"""Repositories for the user's taste memory: profile, feedback, references, watchlist,
rejections, preference rules, actor preferences and franchise dependencies."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mris.models import (
    ActorPreference,
    FranchiseDependency,
    Movie,
    MovieFeedback,
    PreferenceRule,
    ReferenceMovie,
    RejectedMovie,
    User,
    WatchlistEntry,
)
from mris.models.tables import utcnow
from mris.text import normalize_text


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def default(self) -> User:
        user = self.s.scalar(select(User).order_by(User.id).limit(1))
        if user is None:
            raise LookupError("No user profile found. Run `mris init` first.")
        return user

    def get_or_create(self, name: str, **fields: Any) -> tuple[User, bool]:
        user = self.s.scalar(select(User).where(User.name == name))
        if user:
            return user, False
        user = User(name=name, **fields)
        self.s.add(user)
        self.s.flush()
        return user, True


class FeedbackRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(self, user: User, movie: Movie, rating_label: str, **fields: Any) -> MovieFeedback:
        fb = MovieFeedback(user_id=user.id, movie_id=movie.id, rating_label=rating_label, **fields)
        self.s.add(fb)
        self.s.flush()
        return fb

    def latest(self, user: User, movie: Movie) -> MovieFeedback | None:
        return self.s.scalar(
            select(MovieFeedback)
            .where(MovieFeedback.user_id == user.id, MovieFeedback.movie_id == movie.id)
            .order_by(MovieFeedback.created_at.desc(), MovieFeedback.id.desc())
            .limit(1)
        )

    def list(self, user: User, rating_label: str | None = None) -> list[MovieFeedback]:
        stmt = select(MovieFeedback).where(MovieFeedback.user_id == user.id)
        if rating_label:
            stmt = stmt.where(MovieFeedback.rating_label == rating_label)
        return list(self.s.scalars(stmt.order_by(MovieFeedback.created_at.desc(), MovieFeedback.id.desc())))

    def latest_per_movie(self, user: User) -> list[MovieFeedback]:
        latest: dict[int, MovieFeedback] = {}
        for fb in reversed(self.list(user)):
            latest[fb.movie_id] = fb
        return list(latest.values())

    def counts_by_label(self, user: User) -> dict[str, int]:
        counts: dict[str, int] = {}
        for fb in self.latest_per_movie(user):
            counts[fb.rating_label] = counts.get(fb.rating_label, 0) + 1
        return counts


class ReferenceRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def upsert(self, user: User, movie: Movie, rating_label: str, importance: str, notes: str | None = None):
        ref = self.s.scalar(
            select(ReferenceMovie).where(
                ReferenceMovie.user_id == user.id, ReferenceMovie.movie_id == movie.id
            )
        )
        if ref is None:
            ref = ReferenceMovie(
                user_id=user.id, movie_id=movie.id, rating_label=rating_label, importance=importance
            )
            self.s.add(ref)
        else:
            ref.rating_label = rating_label
            rank = {"low": 0, "medium": 1, "high": 2, "very_high": 3}
            if rank.get(importance, 0) > rank.get(ref.importance, 0):
                ref.importance = importance  # never downgrade a reference the user ranked higher
        if notes and not ref.notes:
            ref.notes = notes
        self.s.flush()
        return ref

    def remove(self, user: User, movie: Movie) -> None:
        ref = self.s.scalar(
            select(ReferenceMovie).where(
                ReferenceMovie.user_id == user.id, ReferenceMovie.movie_id == movie.id
            )
        )
        if ref:
            self.s.delete(ref)

    def list(self, user: User) -> list[ReferenceMovie]:
        return list(self.s.scalars(select(ReferenceMovie).where(ReferenceMovie.user_id == user.id)))


class WatchlistRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, user: User, movie: Movie) -> WatchlistEntry | None:
        return self.s.scalar(
            select(WatchlistEntry).where(
                WatchlistEntry.user_id == user.id, WatchlistEntry.movie_id == movie.id
            )
        )

    def add(self, user: User, movie: Movie, note: str | None = None) -> WatchlistEntry:
        entry = self.get(user, movie)
        if entry is None:
            entry = WatchlistEntry(user_id=user.id, movie_id=movie.id, note=note)
            self.s.add(entry)
        else:
            entry.status = "watch_later"
            if note:
                entry.note = note
        self.s.flush()
        return entry

    def set_status(self, user: User, movie: Movie, status: str) -> WatchlistEntry | None:
        entry = self.get(user, movie)
        if entry:
            entry.status = status
        return entry

    def list(self, user: User, status: str | None = "watch_later") -> list[WatchlistEntry]:
        stmt = select(WatchlistEntry).where(WatchlistEntry.user_id == user.id)
        if status:
            stmt = stmt.where(WatchlistEntry.status == status)
        return list(self.s.scalars(stmt.order_by(WatchlistEntry.added_at)))


class RejectedRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(
        self,
        user: User,
        movie: Movie,
        reason: str,
        source: str,
        confidence: str = "HIGH",
    ) -> RejectedMovie:
        existing = self.get(user, movie)
        if existing:
            if source.startswith("user") and not existing.source_of_rejection.startswith("user"):
                existing.source_of_rejection = source
                existing.rejection_reason = reason
                existing.confidence = confidence
            return existing
        row = RejectedMovie(
            user_id=user.id,
            movie_id=movie.id,
            title=movie.title,
            year=movie.year,
            rejection_reason=reason,
            source_of_rejection=source,
            confidence=confidence,
            rejection_date=utcnow(),
        )
        self.s.add(row)
        self.s.flush()
        return row

    def get(self, user: User, movie: Movie) -> RejectedMovie | None:
        return self.s.scalar(
            select(RejectedMovie).where(RejectedMovie.user_id == user.id, RejectedMovie.movie_id == movie.id)
        )

    def remove(self, user: User, movie: Movie) -> bool:
        row = self.get(user, movie)
        if row:
            self.s.delete(row)
            return True
        return False

    def list(self, user: User, source: str | None = None) -> list[RejectedMovie]:
        stmt = select(RejectedMovie).where(RejectedMovie.user_id == user.id)
        if source:
            stmt = stmt.where(RejectedMovie.source_of_rejection.startswith(source))
        return list(self.s.scalars(stmt.order_by(RejectedMovie.rejection_date.desc())))

    def count(self, user: User) -> int:
        return (
            self.s.scalar(select(func.count(RejectedMovie.id)).where(RejectedMovie.user_id == user.id)) or 0
        )


class PreferenceRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, user: User, rule_type: str, key: str) -> PreferenceRule | None:
        return self.s.scalar(
            select(PreferenceRule).where(
                PreferenceRule.user_id == user.id,
                PreferenceRule.rule_type == rule_type,
                PreferenceRule.key == key,
            )
        )

    def set(
        self,
        user: User,
        rule_type: str,
        key: str,
        value: float,
        source: str = "user",
        notes: str | None = None,
        enabled: bool = True,
    ) -> PreferenceRule:
        rule = self.get(user, rule_type, key)
        if rule is None:
            rule = PreferenceRule(user_id=user.id, rule_type=rule_type, key=key)
            self.s.add(rule)
        rule.value, rule.source, rule.enabled = float(value), source, enabled
        if notes:
            rule.notes = notes
        self.s.flush()
        return rule

    def ensure(self, user: User, rule_type: str, key: str, value: float, notes: str | None = None) -> None:
        """Seed a rule without overwriting a learned/user-edited value."""
        if self.get(user, rule_type, key) is None:
            self.set(user, rule_type, key, value, source="seed", notes=notes)

    def adjust(
        self,
        user: User,
        rule_type: str,
        key: str,
        delta: float,
        lo: float,
        hi: float,
        source: str = "learning",
        notes: str | None = None,
    ) -> PreferenceRule:
        rule = self.get(user, rule_type, key)
        base = rule.value if rule else 0.0
        return self.set(user, rule_type, key, max(lo, min(hi, base + delta)), source=source, notes=notes)

    def values(self, user: User, rule_type: str, enabled_only: bool = True) -> dict[str, float]:
        stmt = select(PreferenceRule).where(
            PreferenceRule.user_id == user.id, PreferenceRule.rule_type == rule_type
        )
        if enabled_only:
            stmt = stmt.where(PreferenceRule.enabled.is_(True))
        return {r.key: r.value for r in self.s.scalars(stmt)}

    def list(self, user: User) -> list[PreferenceRule]:
        return list(
            self.s.scalars(
                select(PreferenceRule)
                .where(PreferenceRule.user_id == user.id)
                .order_by(PreferenceRule.rule_type, PreferenceRule.key)
            )
        )


class ActorPreferenceRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(
        self,
        user: User,
        actor_name: str,
        sentiment: float,
        scope: str = "movie",
        movie: Movie | None = None,
        reason: str | None = None,
    ) -> ActorPreference:
        row = ActorPreference(
            user_id=user.id,
            actor_name=actor_name,
            normalized_name=normalize_text(actor_name),
            scope=scope,
            movie_id=movie.id if movie else None,
            sentiment=sentiment,
            reason=reason,
        )
        self.s.add(row)
        self.s.flush()
        return row

    def for_actor(self, user: User, actor_name: str) -> list[ActorPreference]:
        return list(
            self.s.scalars(
                select(ActorPreference).where(
                    ActorPreference.user_id == user.id,
                    ActorPreference.normalized_name == normalize_text(actor_name),
                )
            )
        )

    def list(self, user: User) -> list[ActorPreference]:
        return list(self.s.scalars(select(ActorPreference).where(ActorPreference.user_id == user.id)))


class FranchiseRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(
        self,
        franchise_name: str,
        movie: Movie | None = None,
        dependency_level: str = "strong",
        franchise_rejected: bool = False,
        notes: str | None = None,
    ) -> FranchiseDependency:
        stmt = select(FranchiseDependency).where(FranchiseDependency.franchise_name == franchise_name)
        stmt = stmt.where(
            FranchiseDependency.movie_id == movie.id if movie else FranchiseDependency.movie_id.is_(None)
        )
        row = self.s.scalar(stmt)
        if row is None:
            row = FranchiseDependency(franchise_name=franchise_name, movie_id=movie.id if movie else None)
            self.s.add(row)
        row.dependency_level, row.franchise_rejected = dependency_level, franchise_rejected
        if notes:
            row.notes = notes
        self.s.flush()
        return row

    def for_movie(self, movie: Movie) -> FranchiseDependency | None:
        return self.s.scalar(select(FranchiseDependency).where(FranchiseDependency.movie_id == movie.id))

    def rejected_franchises(self) -> set[str]:
        rows = self.s.scalars(
            select(FranchiseDependency).where(FranchiseDependency.franchise_rejected.is_(True))
        )
        return {normalize_text(r.franchise_name) for r in rows}

    def list(self) -> list[FranchiseDependency]:
        return list(self.s.scalars(select(FranchiseDependency)))
