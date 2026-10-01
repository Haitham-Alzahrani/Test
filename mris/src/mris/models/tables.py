"""SQLAlchemy ORM models.

The schema itself is owned by Alembic migrations (``migrations/versions``); these classes must
stay in sync with them.  ``tests/integration/test_migrations.py`` verifies that.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    primary_language: Mapped[str] = mapped_column(String(10), default="ar")
    response_language: Mapped[str] = mapped_column(String(10), default="ar")
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        Index("ix_movies_normalized_title_year", "normalized_title", "year"),
        Index("ix_movies_release_date", "release_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    normalized_title: Mapped[str] = mapped_column(String(300), index=True)
    year: Mapped[int | None] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(10), default="movie")  # movie | tv
    release_date: Mapped[date | None] = mapped_column(Date)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    imdb_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    original_language: Mapped[str | None] = mapped_column(String(10))
    countries: Mapped[list[Any]] = mapped_column(JSON, default=list)
    genres: Mapped[list[Any]] = mapped_column(JSON, default=list)
    keywords: Mapped[list[Any]] = mapped_column(JSON, default=list)
    runtime: Mapped[int | None] = mapped_column(Integer)
    director: Mapped[str | None] = mapped_column(String(200))
    cast: Mapped[list[Any]] = mapped_column(JSON, default=list)  # [{"name":..,"popularity":..,"order":..}]
    overview: Mapped[str | None] = mapped_column(Text)
    collection_name: Mapped[str | None] = mapped_column(String(300))
    collection_position: Mapped[int | None] = mapped_column(Integer)  # 1 = first film in collection
    budget: Mapped[int | None] = mapped_column(Integer)
    production_companies: Mapped[list[Any]] = mapped_column(JSON, default=list)
    trailer_url: Mapped[str | None] = mapped_column(String(500))
    ratings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # {"imdb": 7.1, "rt": 81, ...}
    metadata_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    aliases: Mapped[list[MovieAlias]] = relationship(back_populates="movie", cascade="all, delete-orphan")
    traits: Mapped[list[MovieTrait]] = relationship(back_populates="movie", cascade="all, delete-orphan")

    @property
    def label(self) -> str:
        return f"{self.title} ({self.year})" if self.year else self.title


class MovieAlias(Base):
    __tablename__ = "movie_aliases"
    __table_args__ = (UniqueConstraint("movie_id", "normalized_alias", name="uq_alias_movie"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(300))
    normalized_alias: Mapped[str] = mapped_column(String(300), index=True)
    language: Mapped[str | None] = mapped_column(String(10))

    movie: Mapped[Movie] = relationship(back_populates="aliases")


class MovieFeedback(Base):
    __tablename__ = "movie_feedback"
    __table_args__ = (Index("ix_feedback_user_movie", "user_id", "movie_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="watched")
    rating_label: Mapped[str] = mapped_column(String(30))
    rating_value: Mapped[float | None] = mapped_column(Float)  # e.g. 7 (out of 10) when the user gave one
    reason_text: Mapped[str | None] = mapped_column(Text)
    positive_traits: Mapped[list[Any]] = mapped_column(JSON, default=list)
    negative_traits: Mapped[list[Any]] = mapped_column(JSON, default=list)
    importance_for_learning: Mapped[str] = mapped_column(String(20), default="medium")
    source: Mapped[str] = mapped_column(String(30), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    movie: Mapped[Movie] = relationship()


class ReferenceMovie(Base):
    __tablename__ = "reference_movies"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_reference_user_movie"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    rating_label: Mapped[str] = mapped_column(String(30))
    importance: Mapped[str] = mapped_column(String(20), default="high")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    movie: Mapped[Movie] = relationship()


class MovieTrait(Base):
    __tablename__ = "movie_traits"
    __table_args__ = (UniqueConstraint("movie_id", "trait", "source", name="uq_trait_movie_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    trait: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float] = mapped_column(Float, default=1.0)  # 0..1 strength
    source: Mapped[str] = mapped_column(String(30), default="user")  # user | seed | research | metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    movie: Mapped[Movie] = relationship(back_populates="traits")


class WatchlistEntry(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_watchlist_user_movie"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="watch_later", index=True)
    note: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    movie: Mapped[Movie] = relationship()


class RejectedMovie(Base):
    __tablename__ = "rejected_movies"
    __table_args__ = (Index("ix_rejected_user_movie", "user_id", "movie_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    year: Mapped[int | None] = mapped_column(Integer)
    rejection_reason: Mapped[str] = mapped_column(Text)
    rejection_date: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    source_of_rejection: Mapped[str] = mapped_column(String(40))  # user | user_trailer | research_pipeline
    confidence: Mapped[str] = mapped_column(String(10), default="HIGH")

    movie: Mapped[Movie] = relationship()


class CandidateMovie(Base):
    """One researched candidate with every assessed dimension stored explicitly."""

    __tablename__ = "candidate_movies"

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), unique=True)
    discovery_source: Mapped[str] = mapped_column(String(60))
    release_category: Mapped[str] = mapped_column(String(20), default="unknown")
    research_status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    research_version: Mapped[int] = mapped_column(Integer, default=0)

    # Opening quality model
    opening_score: Mapped[float | None] = mapped_column(Float)
    opening_confidence: Mapped[str | None] = mapped_column(String(10))
    opening_evidence: Mapped[list[Any]] = mapped_column(JSON, default=list)
    opening_event_start_minutes: Mapped[float | None] = mapped_column(Float)
    pacing: Mapped[float | None] = mapped_column(Float)
    slow_burn: Mapped[bool] = mapped_column(Boolean, default=False)

    # Story progression model
    story_clarity: Mapped[float | None] = mapped_column(Float)
    story_progression: Mapped[float | None] = mapped_column(Float)
    event_continuity: Mapped[float | None] = mapped_column(Float)
    plot_coherence: Mapped[float | None] = mapped_column(Float)
    dialogue_to_event_ratio: Mapped[float | None] = mapped_column(Float)  # 1 = action/events dominate
    tension_continuity: Mapped[float | None] = mapped_column(Float)
    action_quality: Mapped[float | None] = mapped_column(Float)

    # Acting / cast model
    cast_strength: Mapped[float | None] = mapped_column(Float)
    acting_quality: Mapped[float | None] = mapped_column(Float)
    character_credibility: Mapped[float | None] = mapped_column(Float)

    # Production model
    production_quality: Mapped[float | None] = mapped_column(Float)
    cinematography_quality: Mapped[float | None] = mapped_column(Float)
    action_clarity: Mapped[float | None] = mapped_column(Float)
    camera_stability: Mapped[float | None] = mapped_column(Float)
    visual_quality: Mapped[float | None] = mapped_column(Float)

    # Realism model
    realism: Mapped[float | None] = mapped_column(Float)
    internal_logic: Mapped[float | None] = mapped_column(Float)
    exaggeration_level: Mapped[float | None] = mapped_column(Float)

    franchise_dependency: Mapped[str | None] = mapped_column(String(20))  # none | partial | strong
    reference_similarity: Mapped[float | None] = mapped_column(Float)
    similar_references: Mapped[list[Any]] = mapped_column(JSON, default=list)
    risks: Mapped[list[Any]] = mapped_column(JSON, default=list)
    strengths: Mapped[list[Any]] = mapped_column(JSON, default=list)
    hard_exclusion_reason: Mapped[str | None] = mapped_column(Text)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    total_score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[str | None] = mapped_column(String(10))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    movie: Mapped[Movie] = relationship()
    sources: Mapped[list[ResearchSource]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class ResearchQueueItem(Base):
    __tablename__ = "research_queue"
    __table_args__ = (
        UniqueConstraint("year", "month", "movie_id", name="uq_queue_period_movie"),
        Index("ix_queue_period_order", "year", "month", "sort_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidate_movies.id", ondelete="SET NULL"))
    candidate: Mapped[str] = mapped_column(String(300))  # display title
    discovery_source: Mapped[str] = mapped_column(String(60))
    release_category: Mapped[str] = mapped_column(String(20), default="unknown")
    release_date: Mapped[date | None] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    research_status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime)
    next_action: Mapped[str | None] = mapped_column(String(200))

    movie: Mapped[Movie] = relationship()


class ResearchEvent(Base):
    __tablename__ = "research_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_movies.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(40))  # step | discovery | cursor | error | decision
    step: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ResearchSource(Base):
    __tablename__ = "research_sources"
    __table_args__ = (UniqueConstraint("candidate_id", "url", name="uq_source_candidate_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_movies.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(1000))
    domain: Mapped[str | None] = mapped_column(String(200))
    publisher: Mapped[str | None] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(500))
    snippet: Mapped[str | None] = mapped_column(Text)
    query: Mapped[str | None] = mapped_column(String(500))
    reliability: Mapped[float] = mapped_column(Float, default=0.5)
    signals: Mapped[list[Any]] = mapped_column(JSON, default=list)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    candidate: Mapped[CandidateMovie] = relationship(back_populates="sources")


class ResearchCursor(Base):
    __tablename__ = "research_cursor"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    month_discovered: Mapped[bool] = mapped_column(Boolean, default=False)
    last_queue_item_id: Mapped[int | None] = mapped_column(Integer)
    last_candidate: Mapped[str | None] = mapped_column(String(300))
    range_start_year: Mapped[int] = mapped_column(Integer)
    range_end_year: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | exhausted
    candidates_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    candidates_rejected: Mapped[int] = mapped_column(Integer, default=0)
    candidates_passed: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PreferenceRule(Base):
    __tablename__ = "preference_rules"
    __table_args__ = (UniqueConstraint("user_id", "rule_type", "key", name="uq_rule_user_type_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rule_type: Mapped[str] = mapped_column(String(20), index=True)
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[float] = mapped_column(Float, default=0.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(40), default="seed")
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ActorPreference(Base):
    __tablename__ = "actor_preferences"
    __table_args__ = (Index("ix_actor_pref_name", "normalized_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    actor_name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200))
    scope: Mapped[str] = mapped_column(String(20), default="movie")  # movie | universal
    movie_id: Mapped[int | None] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    sentiment: Mapped[float] = mapped_column(Float, default=-1.0)  # -1 dislike .. +1 like
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FranchiseDependency(Base):
    __tablename__ = "franchise_dependencies"
    __table_args__ = (Index("ix_franchise_name", "franchise_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    franchise_name: Mapped[str] = mapped_column(String(200))
    movie_id: Mapped[int | None] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    dependency_level: Mapped[str] = mapped_column(String(20), default="strong")  # none | partial | strong
    franchise_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RecommendationHistory(Base):
    __tablename__ = "recommendation_history"
    __table_args__ = (Index("ix_rec_user_movie", "user_id", "movie_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidate_movies.id", ondelete="SET NULL"))
    recommended_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[str | None] = mapped_column(String(10))
    reason: Mapped[str | None] = mapped_column(Text)
    research_version: Mapped[int] = mapped_column(Integer, default=1)
    user_response: Mapped[str] = mapped_column(String(20), default="pending")
    responded_at: Mapped[datetime | None] = mapped_column(DateTime)

    movie: Mapped[Movie] = relationship()
