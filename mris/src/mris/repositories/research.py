"""Repositories for research state: cursor, queue, candidates, sources, events, recommendations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mris.models import (
    CandidateMovie,
    Movie,
    RecommendationHistory,
    ResearchCursor,
    ResearchEvent,
    ResearchQueueItem,
    ResearchSource,
    User,
)
from mris.models.enums import RELEASE_CATEGORY_ORDER
from mris.models.tables import utcnow


class CursorRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, user: User) -> ResearchCursor | None:
        return self.s.scalar(select(ResearchCursor).where(ResearchCursor.user_id == user.id))

    def get_or_create(self, user: User, start_year: int, end_year: int) -> ResearchCursor:
        cursor = self.get(user)
        if cursor is None:
            cursor = ResearchCursor(
                user_id=user.id,
                year=start_year,
                month=1,
                range_start_year=start_year,
                range_end_year=end_year,
                status="active",
                candidates_evaluated=0,
                candidates_rejected=0,
                candidates_passed=0,
                month_discovered=False,
            )
            self.s.add(cursor)
            self.s.flush()
        return cursor


class QueueRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def for_period(self, year: int, month: int) -> list[ResearchQueueItem]:
        return list(
            self.s.scalars(
                select(ResearchQueueItem)
                .where(ResearchQueueItem.year == year, ResearchQueueItem.month == month)
                .order_by(ResearchQueueItem.sort_order, ResearchQueueItem.id)
            )
        )

    def get(self, year: int, month: int, movie: Movie) -> ResearchQueueItem | None:
        return self.s.scalar(
            select(ResearchQueueItem).where(
                ResearchQueueItem.year == year,
                ResearchQueueItem.month == month,
                ResearchQueueItem.movie_id == movie.id,
            )
        )

    def add(
        self, year: int, month: int, movie: Movie, discovery_source: str, release_category: str
    ) -> ResearchQueueItem:
        item = self.get(year, month, movie)
        if item is None:
            item = ResearchQueueItem(
                year=year,
                month=month,
                movie_id=movie.id,
                candidate=movie.label,
                discovery_source=discovery_source,
                release_category=release_category,
                release_date=movie.release_date,
                research_status="queued",
                next_action="research",
            )
            self.s.add(item)
            self.s.flush()
        return item

    def reorder(self, year: int, month: int) -> None:
        """Deterministic order: release category priority, then release date, then title."""
        items = self.for_period(year, month)
        items.sort(
            key=lambda i: (
                RELEASE_CATEGORY_ORDER.get(i.release_category, 9),
                i.release_date.isoformat() if i.release_date else "9999",
                i.candidate.lower(),
            )
        )
        for pos, item in enumerate(items):
            item.sort_order = pos
        self.s.flush()

    def pending(self, year: int, month: int) -> list[ResearchQueueItem]:
        return [i for i in self.for_period(year, month) if i.research_status in ("queued", "in_progress")]

    def list(self, status: str | None = None, limit: int = 300) -> list[ResearchQueueItem]:
        stmt = select(ResearchQueueItem)
        if status:
            stmt = stmt.where(ResearchQueueItem.research_status == status)
        stmt = stmt.order_by(
            ResearchQueueItem.year.desc(), ResearchQueueItem.month, ResearchQueueItem.sort_order
        ).limit(limit)
        return list(self.s.scalars(stmt))


class CandidateRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, candidate_id: int) -> CandidateMovie | None:
        return self.s.get(CandidateMovie, candidate_id)

    def for_movie(self, movie: Movie) -> CandidateMovie | None:
        return self.s.scalar(select(CandidateMovie).where(CandidateMovie.movie_id == movie.id))

    def get_or_create(
        self, movie: Movie, discovery_source: str, release_category: str = "unknown"
    ) -> CandidateMovie:
        cand = self.for_movie(movie)
        if cand is None:
            cand = CandidateMovie(
                movie_id=movie.id,
                discovery_source=discovery_source,
                release_category=release_category,
                research_status="queued",
                research_version=0,
            )
            self.s.add(cand)
            self.s.flush()
        return cand

    def by_status(self, status: str) -> list[CandidateMovie]:
        return list(
            self.s.scalars(
                select(CandidateMovie)
                .where(CandidateMovie.research_status == status)
                .order_by(CandidateMovie.total_score.desc().nulls_last())
            )
        )

    def count_by_status(self) -> dict[str, int]:
        rows = self.s.execute(
            select(CandidateMovie.research_status, func.count(CandidateMovie.id)).group_by(
                CandidateMovie.research_status
            )
        )
        return {status: count for status, count in rows}

    def add_source(self, candidate: CandidateMovie, **fields: Any) -> ResearchSource:
        url = fields["url"]
        src = self.s.scalar(
            select(ResearchSource).where(
                ResearchSource.candidate_id == candidate.id, ResearchSource.url == url
            )
        )
        if src is None:
            src = ResearchSource(candidate_id=candidate.id, **fields)
            self.s.add(src)
        else:
            for key, value in fields.items():
                if value is not None:
                    setattr(src, key, value)
            src.retrieved_at = utcnow()
        self.s.flush()
        return src

    def sources(self, candidate: CandidateMovie) -> list[ResearchSource]:
        return list(self.s.scalars(select(ResearchSource).where(ResearchSource.candidate_id == candidate.id)))


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def log(
        self,
        event_type: str,
        message: str,
        candidate: CandidateMovie | None = None,
        step: int | None = None,
        **data: Any,
    ) -> ResearchEvent:
        ev = ResearchEvent(
            candidate_id=candidate.id if candidate else None,
            event_type=event_type,
            step=step,
            message=message,
            data=data,
        )
        self.s.add(ev)
        return ev

    def for_candidate(self, candidate: CandidateMovie) -> list[ResearchEvent]:
        return list(
            self.s.scalars(
                select(ResearchEvent)
                .where(ResearchEvent.candidate_id == candidate.id)
                .order_by(ResearchEvent.id)
            )
        )

    def recent(self, limit: int = 50) -> list[ResearchEvent]:
        return list(self.s.scalars(select(ResearchEvent).order_by(ResearchEvent.id.desc()).limit(limit)))


class RecommendationRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(self, user: User, candidate: CandidateMovie, reason: str) -> RecommendationHistory:
        rec = RecommendationHistory(
            user_id=user.id,
            movie_id=candidate.movie_id,
            candidate_id=candidate.id,
            score=candidate.total_score,
            confidence=candidate.confidence,
            reason=reason,
            research_version=candidate.research_version,
            user_response="pending",
        )
        self.s.add(rec)
        self.s.flush()
        return rec

    def for_movie(self, user: User, movie: Movie) -> list[RecommendationHistory]:
        return list(
            self.s.scalars(
                select(RecommendationHistory).where(
                    RecommendationHistory.user_id == user.id, RecommendationHistory.movie_id == movie.id
                )
            )
        )

    def latest(self, user: User) -> RecommendationHistory | None:
        return self.s.scalar(
            select(RecommendationHistory)
            .where(RecommendationHistory.user_id == user.id)
            .order_by(RecommendationHistory.recommended_at.desc(), RecommendationHistory.id.desc())
            .limit(1)
        )

    def respond(self, user: User, movie: Movie, response: str) -> None:
        for rec in self.for_movie(user, movie):
            if rec.user_response == "pending" or response != "pending":
                rec.user_response = response
                rec.responded_at = utcnow()

    def list(self, user: User, limit: int = 100) -> list[RecommendationHistory]:
        return list(
            self.s.scalars(
                select(RecommendationHistory)
                .where(RecommendationHistory.user_id == user.id)
                .order_by(RecommendationHistory.recommended_at.desc(), RecommendationHistory.id.desc())
                .limit(limit)
            )
        )
