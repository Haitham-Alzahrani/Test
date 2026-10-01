"""Application service: the single entry point used by the CLI, the API and the web UI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mris.config import Settings, get_settings
from mris.memory import (
    parse_message,
    record_cast_rejection,
    record_feedback,
    record_preference_statement,
    seed_initial_data,
)
from mris.memory.parser import (
    INTENT_CAST_REJECT,
    INTENT_CONTINUE,
    INTENT_FEEDBACK,
    INTENT_PREFERENCE,
    INTENT_RECOMMEND,
    INTENT_WATCH_LATER,
)
from mris.models import CandidateMovie, Movie, ResearchStatus, User
from mris.recommendation import Recommendation, RecommendationEngine, format_explanation
from mris.repositories import Repos
from mris.research.engine import ResearchEngine, RunResult
from mris.research.evidence import detect_themes, extract_signals
from mris.research.pipeline import ResearchPipeline, apply_metadata
from mris.search.base import ProviderError
from mris.search.factory import Providers, build_providers
from mris.search.sources import classify_source, domain_of
from mris.text import normalize_title, truncate

MSG = {
    "ar": {
        "no_title": 'لم أتعرّف على اسم الفيلم. اكتب الاسم بالإنجليزية أو استخدم: mris feedback "Title" --rating ...',
        "saved_feedback": "تم حفظ رأيك في {title}.",
        "watchlist": "تمت إضافة {title} لقائمة المشاهدة لاحقًا.",
        "cast": "تم تسجيل أن طاقم {title} لا يناسبك، ولن يُقترح مرة أخرى.",
        "pref": "تم تحديث تفضيلاتك.",
        "searching_done": "انتهى نطاق البحث المحدد بالكامل دون العثور على فيلم بثقة عالية.",
        "stopped": "توقف البحث مؤقتًا: {reason}. الموضع محفوظ ({position}) — اكتب «اكمل» للمتابعة.",
        "unknown": "لم أفهم الطلب. أمثلة: «اكمل»، «اقترح فيلم»، «Mutiny عجبني جدًا»، «ضعه للمشاهدة لاحقًا».",
        "no_last": "لا يوجد اقتراح سابق أربطه بهذا الرد. اذكر اسم الفيلم.",
    },
    "en": {
        "no_title": 'I couldn\'t identify the movie title. Use: mris feedback "Title" --rating ...',
        "saved_feedback": "Saved your feedback on {title}.",
        "watchlist": "{title} added to watch-later.",
        "cast": "Noted that the cast of {title} doesn't appeal to you; it won't be suggested again.",
        "pref": "Preferences updated.",
        "searching_done": "The configured search range is exhausted with no HIGH-confidence match.",
        "stopped": "Search paused: {reason}. Position saved ({position}) — say 'continue' to resume.",
        "unknown": "I didn't understand. Examples: 'continue', 'recommend', 'Mutiny loved it', 'watch later'.",
        "no_last": "There is no previous recommendation to attach this to. Please name the movie.",
    },
}


@dataclass
class Reply:
    text: str
    data: dict[str, Any] = field(default_factory=dict)


class MRIS:
    def __init__(
        self,
        session: Session,
        providers: Providers | None = None,
        settings: Settings | None = None,
        today: date | None = None,
    ) -> None:
        self.session = session
        self.repos = Repos(session)
        self.settings = settings or get_settings()
        self.providers = providers if providers is not None else build_providers(self.settings)
        self.today = today
        self._pipeline: ResearchPipeline | None = None

    # ----------------------------------------------------------------- basics
    @property
    def user(self) -> User:
        return self.repos.users.default()

    @property
    def lang(self) -> str:
        return self.user.response_language if self.user.response_language in MSG else "ar"

    def _msg(self, key: str, **kw: Any) -> str:
        return MSG[self.lang][key].format(**kw)

    def init(self) -> tuple[User, bool]:
        user, created = seed_initial_data(self.repos)
        self.session.commit()
        return user, created

    @property
    def pipeline(self) -> ResearchPipeline:
        if self._pipeline is None:
            self._pipeline = ResearchPipeline(self.repos, self.user, self.providers, self.settings)
        return self._pipeline

    def engine(self) -> ResearchEngine:
        return ResearchEngine(
            self.repos,
            self.user,
            self.providers,
            self.settings,
            commit=self.session.commit,
            today=self.today,
            pipeline=self.pipeline,
        )

    def resolve_movie(self, title: str, year: int | None = None, create: bool = True) -> Movie | None:
        movie = self.repos.movies.find(title, year)
        if movie is None and create:
            movie, _ = self.repos.movies.get_or_create(title, year)
        return movie

    # ----------------------------------------------------------------- status
    def status(self) -> dict[str, Any]:
        user = self.user
        engine = self.engine()
        cursor = engine.cursor()
        counts = self.repos.feedback.counts_by_label(user)
        watched = sum(counts.values())
        return {
            "user": user.name,
            "watched": watched,
            "loved": counts.get("loved", 0) + counts.get("excellent", 0),
            "liked": counts.get("liked", 0) + counts.get("good", 0),
            "medium": counts.get("medium", 0) + counts.get("average", 0) + counts.get("medium_low", 0),
            "disliked": counts.get("disliked", 0),
            "watchlist": len(self.repos.watchlist.list(user)),
            "rejected": self.repos.rejected.count(user),
            "references": len(self.repos.references.list(user)),
            "candidates": self.repos.candidates.count_by_status(),
            "recommendations": len(self.repos.recommendations.list(user, limit=10_000)),
            "cursor": {
                "position": engine.position(),
                "year": cursor.year,
                "month": cursor.month,
                "status": cursor.status,
                "last_candidate": cursor.last_candidate,
                "evaluated": cursor.candidates_evaluated,
                "rejected": cursor.candidates_rejected,
                "passed": cursor.candidates_passed,
                "range": f"{cursor.range_start_year} → {cursor.range_end_year}",
            },
            "providers": self.providers.describe(),
            "movies": self.session.scalar(select(func.count(Movie.id))) or 0,
        }

    # ----------------------------------------------------------------- research
    def continue_search(
        self,
        year: int | None = None,
        month: int | None = None,
        max_candidates: int | None = None,
        progress: Callable[[str], None] | None = None,
        show_score: bool = False,
    ) -> tuple[RunResult, Recommendation | None, str]:
        rec_engine = RecommendationEngine(self.repos, self.user)
        # A strong candidate found earlier but never shown comes first.
        ready = rec_engine.recommend(1, self.lang, show_score)
        if ready:
            self.session.commit()
            return RunResult(stopped_reason="strong candidate already researched"), ready[0], ready[0].text
        if self.providers.metadata is not None and not self.user.profile.get("references_enriched"):
            self.enrich_references()
        engine = self.engine()
        if month is not None:
            engine.jump_to(year or engine.cursor().year, month)
        result = engine.continue_search(
            year=year if month is None else None, max_candidates=max_candidates, progress=progress
        )
        rec = None
        if result.found is not None:
            recs = rec_engine.recommend(1, self.lang, show_score)
            rec = recs[0] if recs else None
        self.session.commit()
        if rec:
            return result, rec, rec.text
        if result.exhausted:
            return result, None, self._msg("searching_done")
        return result, None, self._msg("stopped", reason=result.stopped_reason, position=result.position)

    def enrich_references(self) -> int:
        """Give references without listed characteristics a trait vector derived from verified
        metadata (overview + keywords). Runs once automatically when a metadata provider exists."""
        provider = self.providers.metadata
        if provider is None:
            return 0
        n = 0
        for ref in self.repos.references.list(self.user):
            movie = ref.movie
            if self.repos.movies.traits(movie.id) and movie.metadata_verified:
                continue
            try:
                if movie.tmdb_id is None:
                    hits = [
                        h
                        for h in provider.search_title(movie.title, movie.year)
                        if normalize_title(h.title) == movie.normalized_title
                    ]
                    if not hits or self.repos.movies.by_tmdb(hits[0].tmdb_id):
                        continue
                    movie.tmdb_id = hits[0].tmdb_id
                meta = provider.details(movie.tmdb_id)
            except ProviderError:
                continue
            apply_metadata(movie, meta)
            themes = detect_themes(" ".join([meta.overview or "", " ".join(meta.keywords)]))
            traits = {k: min(1.0, 0.6 + 0.2 * c) for k, c in themes.items()}
            if (meta.year or 0) >= 2000:
                traits["modern_setting"] = 1.0
            if traits:
                self.repos.movies.set_traits(movie, traits, source="metadata")
            n += 1
        self.user.profile = {**self.user.profile, "references_enriched": True}
        self.session.commit()
        return n

    def recommend(
        self,
        count: int = 1,
        research: bool = True,
        show_score: bool = False,
        progress: Callable[[str], None] | None = None,
    ) -> list[Recommendation]:
        rec_engine = RecommendationEngine(self.repos, self.user)
        recs = rec_engine.recommend(count, self.lang, show_score)
        while research and len(recs) < count:
            result, rec, _ = self.continue_search(progress=progress, show_score=show_score)
            if rec is None:
                break
            recs.append(rec)
        self.session.commit()
        return recs

    def research_title(self, title: str, year: int | None = None, force: bool = False) -> CandidateMovie:
        """Research one specific title on request (the user asked about it explicitly)."""
        movie = self.resolve_movie(title, year)
        result = self.pipeline.research(movie, "user_request", force=force)
        self.session.commit()
        return result.candidate

    def explain(self, title: str, year: int | None = None) -> str | None:
        movie = self.resolve_movie(title, year, create=False)
        cand = self.repos.candidates.for_movie(movie) if movie else None
        return format_explanation(cand, self.lang) if cand else None

    def queue_candidate(self, title: str, year: int, month: int, category: str = "unknown") -> Movie:
        movie = self.resolve_movie(title, year)
        self.repos.queue.add(year, month, movie, "manual", category)
        self.repos.queue.reorder(year, month)
        self.session.commit()
        return movie

    def add_evidence(
        self,
        title: str,
        year: int | None,
        url: str,
        text: str,
        source_type: str | None = None,
        publisher: str | None = None,
        reevaluate: bool = True,
    ) -> CandidateMovie:
        """Store a real source (URL + the text it contains) and re-score. The text is analysed
        with the same lexicon as automatic research - this is how a human or an AI agent with
        its own web access can feed evidence without any API key."""
        movie = self.resolve_movie(title, year)
        cand = self.repos.candidates.get_or_create(movie, "manual")
        auto_type, auto_pub, reliability = classify_source(url)
        signals = extract_signals(text)
        self.repos.candidates.add_source(
            cand,
            url=url,
            domain=domain_of(url),
            publisher=publisher or auto_pub,
            source_type=source_type or (auto_type if auto_type != "other" else "manual"),
            title=movie.label,
            snippet=truncate(text, 500),
            query="manual evidence",
            reliability=reliability,
            signals=[s.as_dict() for s in signals[:60]],
        )
        self.repos.events.log(
            "evidence", f"manual evidence added from {domain_of(url)}", candidate=cand, signals=len(signals)
        )
        if reevaluate:
            self.pipeline.evaluate(cand)
        self.session.commit()
        return cand

    def rescore_all(self) -> int:
        """Re-evaluate stored candidates with the current taste model (after learning)."""
        n = 0
        for status in (
            ResearchStatus.PASSED,
            ResearchStatus.BORDERLINE,
            ResearchStatus.INSUFFICIENT_EVIDENCE,
        ):
            for cand in self.repos.candidates.by_status(status.value):
                self.pipeline.evaluate(cand)
                n += 1
        self.session.commit()
        return n

    # ----------------------------------------------------------------- memory
    def feedback(
        self,
        title: str,
        rating: str,
        year: int | None = None,
        notes: str | None = None,
        positive: list[str] | None = None,
        negative: list[str] | None = None,
        rating_value: float | None = None,
    ):
        movie = self.resolve_movie(title, year)
        pos, neg = list(positive or []), list(negative or [])
        if notes:
            parsed = parse_message(notes)
            pos += parsed.positive_traits
            neg += parsed.negative_traits
            if rating_value is None:
                rating_value = parsed.rating_value
        report = record_feedback(self.repos, self.user, movie, rating, pos, neg, notes, rating_value)
        self.session.commit()
        return report

    def watchlist_add(self, title: str, year: int | None = None, note: str | None = None) -> Movie:
        movie = self.resolve_movie(title, year)
        self.repos.watchlist.add(self.user, movie, note)
        self.repos.recommendations.respond(self.user, movie, "watch_later")
        self.session.commit()
        return movie

    def watchlist_remove(self, title: str, year: int | None = None) -> bool:
        movie = self.resolve_movie(title, year, create=False)
        if not movie:
            return False
        entry = self.repos.watchlist.set_status(self.user, movie, "removed")
        self.session.commit()
        return entry is not None

    def reject(self, title: str, year: int | None, reason: str, source: str = "user") -> Movie:
        movie = self.resolve_movie(title, year)
        self.repos.rejected.add(self.user, movie, reason, source, "HIGH")
        self.repos.recommendations.respond(self.user, movie, "declined")
        self.session.commit()
        return movie

    def _last_recommended_movie(self) -> Movie | None:
        last = self.repos.recommendations.latest(self.user)
        return last.movie if last else None

    def handle_message(self, text: str, progress: Callable[[str], None] | None = None) -> Reply:
        """Natural-language entry point: «اكمل»، «شاهدته وأعجبني جدًا»، «ضعه للمشاهدة لاحقًا» ..."""
        parsed = parse_message(text, self.repos.movies.known_titles())
        movie = None
        if parsed.intent in (INTENT_FEEDBACK, INTENT_WATCH_LATER, INTENT_CAST_REJECT):
            if parsed.title:
                movie = self.resolve_movie(parsed.title, parsed.year)
            elif parsed.refers_to_last:
                movie = self._last_recommended_movie()
            if movie is None:
                return Reply(
                    self._msg("no_last" if parsed.refers_to_last else "no_title"), {"intent": parsed.intent}
                )

        if parsed.intent == INTENT_CONTINUE:
            result, rec, msg = self.continue_search(year=parsed.year, progress=progress)
            return Reply(msg, {"intent": "continue", "found": rec.candidate.movie.label if rec else None})
        if parsed.intent == INTENT_RECOMMEND:
            recs = self.recommend(1, progress=progress)
            if recs:
                return Reply(recs[0].text, {"intent": "recommend", "found": recs[0].candidate.movie.label})
            _, _, msg = self.continue_search(progress=progress)
            return Reply(msg, {"intent": "recommend", "found": None})
        if parsed.intent == INTENT_FEEDBACK:
            report = record_feedback(
                self.repos,
                self.user,
                movie,
                parsed.rating_label,
                parsed.positive_traits,
                parsed.negative_traits,
                parsed.raw,
                parsed.rating_value,
            )
            self.session.commit()
            return Reply(
                self._msg("saved_feedback", title=movie.label),
                {
                    "intent": "feedback",
                    "rating": parsed.rating_label,
                    "changes": report.changes,
                    "positive": parsed.positive_traits,
                    "negative": parsed.negative_traits,
                },
            )
        if parsed.intent == INTENT_WATCH_LATER:
            self.repos.watchlist.add(self.user, movie, None)
            self.repos.recommendations.respond(self.user, movie, "watch_later")
            self.session.commit()
            return Reply(self._msg("watchlist", title=movie.label), {"intent": "watch_later"})
        if parsed.intent == INTENT_CAST_REJECT:
            report = record_cast_rejection(self.repos, self.user, movie, parsed.universal_actor, parsed.raw)
            self.session.commit()
            return Reply(
                self._msg("cast", title=movie.label), {"intent": "cast_reject", "changes": report.changes}
            )
        if parsed.intent == INTENT_PREFERENCE:
            report = record_preference_statement(
                self.repos, self.user, parsed.positive_traits, parsed.negative_traits, parsed.raw
            )
            self.session.commit()
            return Reply(self._msg("pref"), {"intent": "preference", "changes": report.changes})
        return Reply(self._msg("unknown"), {"intent": "unknown"})
