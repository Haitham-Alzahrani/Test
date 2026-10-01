"""The per-candidate research pipeline (section 16).

STEP 1  discover candidate (done by the engine / caller, logged here)
STEP 2  verify title, year, release date, language, country, genre, runtime, cast, director
STEP 3  professional reviews            STEP 4  audience reaction
STEP 5  opening / pacing                STEP 6  story clarity
STEP 7  acting                          STEP 8  cinematography / action style
STEP 9  franchise dependency            STEP 10 compare with positive & negative references
STEP 11 hard exclusions                 STEP 12 compatibility score
STEP 13 decision - only PASSED (HIGH confidence, above threshold) may ever be shown

Everything the pipeline concludes is traceable to stored `research_sources` rows (with the
matched phrases and quotes) or to provider metadata.  Missing evidence lowers confidence; it is
never filled in.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date

from mris.config import Settings, get_settings
from mris.models import CandidateMovie, Importance, Movie, ResearchStatus, RuleType, User
from mris.models.tables import utcnow
from mris.recommendation.blocklist import block_reason
from mris.repositories import Repos
from mris.research.evidence import EvidenceSummary, Signal, SourceInput, extract_signals
from mris.scoring.assessment import MODERATE, STRONG, assess
from mris.scoring.compatibility import compute_score, decide
from mris.scoring.exclusions import find_exclusions
from mris.scoring.similarity import (
    affinity_score,
    candidate_traits,
    compare,
    reference_dimension,
)
from mris.search.base import AudienceReview, CastMember, MovieMetadata, ProviderError, Ratings, SearchResult
from mris.search.factory import Providers
from mris.search.sources import classify_source, domain_of
from mris.text import normalize_text, normalize_title, truncate

RESEARCH_VERSION = 1

# (step, purpose, query template). {t} = quoted title, {y} = year
QUERY_PLAN: list[tuple[int, str, str]] = [
    (3, "reviews", "{t} {y} movie review"),
    (4, "audience", "{t} {y} movie reddit discussion"),
    (5, "opening", '{t} {y} review slow start OR "opening scene" OR "first act" pacing'),
    (6, "story", '{t} {y} review plot story predictable OR confusing OR "well plotted"'),
    (7, "acting", "{t} {y} review performances cast acting"),
    (8, "cinematography", '{t} {y} review cinematography action scenes "shaky" OR "camera"'),
]
FRANCHISE_QUERY = (9, "franchise", "{t} {y} do you need to see previous movies standalone")


@dataclass
class PipelineResult:
    candidate: CandidateMovie
    status: ResearchStatus
    reason: str


def movie_to_metadata(movie: Movie) -> MovieMetadata:
    return MovieMetadata(
        title=movie.title,
        year=movie.year,
        tmdb_id=movie.tmdb_id,
        imdb_id=movie.imdb_id,
        release_date=movie.release_date,
        original_language=movie.original_language,
        countries=list(movie.countries or []),
        genres=list(movie.genres or []),
        keywords=list(movie.keywords or []),
        runtime=movie.runtime,
        director=movie.director,
        cast=[
            CastMember(name=c.get("name", ""), order=c.get("order", 99), popularity=c.get("popularity"))
            for c in (movie.cast or [])
        ],
        overview=movie.overview,
        collection_name=movie.collection_name,
        collection_position=movie.collection_position,
        budget=movie.budget,
        production_companies=list(movie.production_companies or []),
        trailer_url=movie.trailer_url,
        vote_average=(movie.ratings or {}).get("tmdb"),
        vote_count=(movie.ratings or {}).get("tmdb_votes"),
    )


def apply_metadata(movie: Movie, meta: MovieMetadata) -> None:
    movie.title = meta.title or movie.title
    movie.normalized_title = normalize_title(movie.title)
    movie.year = meta.year or movie.year
    movie.release_date = meta.release_date or movie.release_date
    movie.tmdb_id = meta.tmdb_id or movie.tmdb_id
    movie.imdb_id = meta.imdb_id or movie.imdb_id
    movie.original_language = meta.original_language
    movie.countries = meta.countries
    movie.genres = meta.genres
    movie.keywords = meta.keywords
    movie.runtime = meta.runtime
    movie.director = meta.director
    movie.cast = [
        {"name": c.name, "order": c.order, "popularity": c.popularity, "character": c.character}
        for c in meta.cast
    ]
    movie.overview = meta.overview
    movie.collection_name = meta.collection_name
    movie.collection_position = meta.collection_position
    movie.budget = meta.budget
    movie.production_companies = meta.production_companies
    movie.trailer_url = meta.trailer_url
    ratings = dict(movie.ratings or {})
    if meta.vote_average is not None:
        ratings["tmdb"] = meta.vote_average
        ratings["tmdb_votes"] = meta.vote_count
    movie.ratings = ratings
    movie.metadata_verified = not meta.missing_core_fields()


class ResearchPipeline:
    def __init__(
        self,
        repos: Repos,
        user: User,
        providers: Providers,
        settings: Settings | None = None,
        sleep=time.sleep,
    ) -> None:
        self.repos = repos
        self.user = user
        self.providers = providers
        self.settings = settings or get_settings()
        self._sleep = sleep
        self._last_web_call = 0.0
        self.metadata_cache: dict[int, MovieMetadata] = {}

    # ------------------------------------------------------------------ helpers
    def _log(self, cand: CandidateMovie | None, step: int | None, message: str, **data) -> None:
        self.repos.events.log("step" if step else "info", message, candidate=cand, step=step, **data)

    def _enabled_exclusions(self) -> set[str]:
        return {k for k, v in self.repos.preferences.values(self.user, RuleType.EXCLUSION).items() if v > 0}

    def _thresholds(self) -> tuple[float, float, float]:
        t = self.repos.preferences.values(self.user, RuleType.THRESHOLD)
        return (
            t.get("pass_score", self.settings.pass_threshold),
            t.get("reject_score", self.settings.reject_threshold),
            t.get("max_opening_event_start_minutes", 15.0),
        )

    def _web_search(self, query: str) -> list[SearchResult]:
        if not self.providers.web:
            return []
        wait = self.settings.web_request_delay - (time.monotonic() - self._last_web_call)
        if wait > 0:
            self._sleep(wait)
        self._last_web_call = time.monotonic()
        return self.providers.web.search(query, max_results=self.settings.max_results_per_query)

    # ------------------------------------------------------------------ public API
    def research(
        self,
        movie: Movie,
        discovery_source: str = "manual",
        release_category: str = "unknown",
        force: bool = False,
    ) -> PipelineResult:
        cand = self.repos.candidates.get_or_create(movie, discovery_source, release_category)
        cand.research_status = ResearchStatus.IN_PROGRESS.value
        self._log(cand, 1, f"candidate discovered via {discovery_source}", category=release_category)

        # Cheap gate first: never spend research on something already watched / rejected / listed.
        reason = block_reason(self.repos, self.user, movie, self._enabled_exclusions())
        if reason and not force:
            return self._finish(cand, ResearchStatus.BLOCKED, f"blocked: {reason}")

        meta = self._verify_metadata(cand, movie)
        if movie.metadata_verified and movie.release_date and movie.release_date > date.today():
            return self._finish(cand, ResearchStatus.INSUFFICIENT_EVIDENCE, "not released yet")

        # A metadata-level hard exclusion (genre, language, setting...) makes web research pointless.
        early = find_exclusions(
            meta, None, self._enabled_exclusions(), self.repos.franchises.rejected_franchises()
        )
        if early and not force:
            self._log(cand, 11, "hard exclusion from verified metadata", exclusions=[e.reason for e in early])
            return self._reject(cand, movie, "hard exclusion: " + "; ".join(e.reason for e in early))

        ratings = self._ratings(cand, movie)
        self._collect_audience_reviews(cand, meta.audience_reviews)
        self._web_research(cand, movie)
        return self.evaluate(cand, meta=meta, ratings=ratings)

    def evaluate(
        self, cand: CandidateMovie, meta: MovieMetadata | None = None, ratings: Ratings | None = None
    ) -> PipelineResult:
        """Steps 10-13 from stored evidence (no network). Used after research, after manual
        evidence is added and when re-scoring with an updated taste model."""
        movie = cand.movie
        meta = meta or movie_to_metadata(movie)
        if ratings is None and movie.ratings:
            r = movie.ratings
            ratings = Ratings(
                imdb=r.get("imdb"),
                imdb_votes=r.get("imdb_votes"),
                rotten_tomatoes=r.get("rotten_tomatoes"),
                metacritic=r.get("metacritic"),
            )
        pass_t, reject_t, max_minutes = self._thresholds()

        summary = self._summary(cand)
        dependency = self.repos.franchises.for_movie(movie)
        a = assess(meta, summary, ratings, dependency.dependency_level if dependency else None, max_minutes)
        self._log(
            cand,
            5,
            "opening assessed",
            score=a.get("opening_score"),
            confidence=a.opening_confidence,
            minutes=a.opening_event_start_minutes,
        )

        # STEP 10 - references
        affinities = self.repos.preferences.values(self.user, RuleType.TRAIT_AFFINITY)
        is_modern = "pre_2000_setting" not in {
            e.key for e in find_exclusions(meta, None, {"pre_2000_setting"})
        }
        traits = candidate_traits(a, modern=is_modern)
        positives, negatives = self._reference_vectors()
        pos_matches = compare(traits, positives, affinities)
        neg_matches = compare(traits, negatives, affinities)
        ref_dim = reference_dimension(pos_matches, neg_matches, affinity_score(traits, affinities))
        extra_flags = self._cast_flags(movie)
        if neg_matches and neg_matches[0].similarity >= 0.5:
            extra_flags["negative_reference_similarity"] = MODERATE
            a.flag_reasons["negative_reference_similarity"] = f"similar to {neg_matches[0].title}"
        self._log(
            cand,
            10,
            "reference comparison",
            similar=[(m.title, m.similarity, m.shared) for m in pos_matches[:3]],
            negative=[(m.title, m.similarity, m.shared) for m in neg_matches[:2]],
        )

        # STEP 11 - hard exclusions
        exclusions = find_exclusions(
            meta, a, self._enabled_exclusions(), self.repos.franchises.rejected_franchises()
        )
        self._log(cand, 11, "hard exclusions checked", exclusions=[e.reason for e in exclusions])

        # STEP 12 - score
        weights = self.repos.preferences.values(self.user, RuleType.WEIGHT)
        penalties = self.repos.preferences.values(self.user, RuleType.PENALTY)
        score = compute_score(a, ref_dim, bool(movie.metadata_verified), weights, penalties, extra_flags)
        self._log(
            cand,
            12,
            "compatibility computed",
            total=score.total,
            confidence=score.confidence.value,
            penalties=score.penalties,
        )

        # Persist every explicit field
        for key, value in a.values.items():
            setattr(cand, key, value)
        cand.opening_confidence = a.opening_confidence
        cand.opening_evidence = a.opening_evidence
        cand.opening_event_start_minutes = a.opening_event_start_minutes
        cand.slow_burn = a.slow_burn
        cand.franchise_dependency = a.franchise_dependency
        cand.reference_similarity = ref_dim
        cand.similar_references = [
            {"title": m.title, "similarity": m.similarity, "shared": m.shared} for m in pos_matches[:3]
        ]
        all_flags = {**a.flags, **extra_flags}
        cand.risks = [
            {"flag": f, "severity": sev, "reason": a.flag_reasons.get(f, "")} for f, sev in all_flags.items()
        ]
        cand.strengths = _strengths(score.dimensions, a)
        cand.score_breakdown = score.breakdown()
        cand.total_score = score.total
        cand.confidence = score.confidence.value
        cand.hard_exclusion_reason = "; ".join(e.reason for e in exclusions) or None
        self.repos.movies.set_traits(movie, traits, source="research")

        # STEP 13 - decision
        status, reason = decide(score, [e.reason for e in exclusions], pass_t, reject_t)
        if status == ResearchStatus.REJECTED:
            return self._reject(cand, movie, reason)
        return self._finish(cand, status, reason)

    # ------------------------------------------------------------------ steps
    def _verify_metadata(self, cand: CandidateMovie, movie: Movie) -> MovieMetadata:
        provider = self.providers.metadata
        if provider is None:
            self._log(
                cand,
                2,
                "no metadata provider configured - using stored data only",
                verified=bool(movie.metadata_verified),
            )
            return movie_to_metadata(movie)
        try:
            tmdb_id = movie.tmdb_id
            if tmdb_id is None:
                hits = provider.search_title(movie.title, movie.year)
                exact = [h for h in hits if normalize_text(h.title) == movie.normalized_title]
                pick = (exact or hits or [None])[0]
                tmdb_id = pick.tmdb_id if pick else None
            if tmdb_id is None:
                self._log(cand, 2, "title not found by metadata provider")
                return movie_to_metadata(movie)
            meta = self.metadata_cache.pop(tmdb_id, None) or provider.details(tmdb_id)
        except ProviderError as exc:
            self._log(cand, 2, f"metadata provider error: {exc}")
            return movie_to_metadata(movie)
        other = self.repos.movies.by_tmdb(meta.tmdb_id) if meta.tmdb_id else None
        if other is not None and other.id != movie.id:
            meta.tmdb_id = None  # keep the unique constraint; the other row already owns it
        apply_metadata(movie, meta)
        cand.release_category = (
            meta.release_category if meta.release_category != "unknown" else cand.release_category
        )
        self.repos.candidates.add_source(
            cand,
            url=meta.source_url or f"tmdb:{meta.tmdb_id}",
            domain="themoviedb.org",
            publisher="TMDb",
            source_type="metadata",
            title=movie.label,
            snippet=truncate(meta.overview or "", 400),
            reliability=0.9,
            signals=[],
        )
        missing = meta.missing_core_fields()
        self._log(
            cand,
            2,
            "metadata verified" if not missing else "metadata incomplete",
            missing=missing,
            language=meta.original_language,
            genres=meta.genres,
            runtime=meta.runtime,
            director=meta.director,
            cast=[c.name for c in meta.cast[:4]],
        )
        return meta

    def _ratings(self, cand: CandidateMovie, movie: Movie) -> Ratings | None:
        if not self.providers.ratings:
            return None
        try:
            ratings = self.providers.ratings.ratings(movie.imdb_id, movie.title, movie.year)
        except ProviderError as exc:
            self._log(cand, 4, f"ratings provider error: {exc}")
            return None
        if ratings:
            movie.ratings = {**(movie.ratings or {}), **ratings.as_dict()}
            self.repos.candidates.add_source(
                cand,
                url=ratings.source_url or f"omdb:{movie.imdb_id}",
                domain="imdb.com",
                publisher="OMDb",
                source_type="ratings",
                title=movie.label,
                snippet=str(ratings.as_dict()),
                reliability=0.8,
                signals=[],
            )
            self._log(cand, 4, "ratings collected", **ratings.as_dict())
        return ratings

    def _collect_audience_reviews(self, cand: CandidateMovie, reviews: list[AudienceReview]) -> None:
        for review in reviews[:12]:
            signals = extract_signals(review.content)
            self._store_source(
                cand,
                review.url,
                "audience",
                "TMDb user review",
                review.content,
                signals,
                query="tmdb reviews",
                reliability=0.55,
            )
        if reviews:
            self._log(cand, 4, f"{len(reviews)} TMDb audience reviews analysed")

    def _web_research(self, cand: CandidateMovie, movie: Movie) -> None:
        if not self.providers.web:
            self._log(
                cand,
                3,
                "no web search provider configured - review steps skipped "
                "(add evidence with `mris research add-evidence`)",
            )
            return
        plan = list(QUERY_PLAN)
        needs_franchise_check = bool(movie.collection_name) or any(
            k.lower() in ("sequel", "spin off", "spin-off", "based on video game", "based on comic")
            for k in (movie.keywords or [])
        )
        if needs_franchise_check:
            plan.append(FRANCHISE_QUERY)
        title_q = f'"{movie.title}"'
        fetched_domains: set[str] = set()
        for step, purpose, template in plan:
            query = template.format(t=title_q, y=movie.year or "")
            try:
                results = self._web_search(query)
            except ProviderError as exc:
                self._log(cand, step, f"web search error: {exc}", query=query)
                continue
            used = 0
            for res in results:
                text = f"{res.title}. {res.snippet}"
                if not _mentions_title(text + " " + (res.content or ""), movie):
                    continue
                stype, publisher, reliability = classify_source(res.url)
                body = res.content
                domain = domain_of(res.url)
                if (
                    body is None
                    and self.providers.fetcher
                    and reliability >= 0.45
                    and domain not in fetched_domains
                ):
                    body = self.providers.fetcher.fetch_text(res.url)
                    fetched_domains.add(domain)
                    if body and not _mentions_title(body[:5000], movie):
                        body = None
                signals = extract_signals(res.snippet) + (extract_signals(body) if body else [])
                self._store_source(
                    cand,
                    res.url,
                    stype,
                    publisher,
                    res.snippet,
                    signals,
                    query=query,
                    reliability=reliability,
                    title=res.title,
                )
                used += 1
            self._log(cand, step, f"{purpose}: {used} relevant sources", query=query)

    # ------------------------------------------------------------------ evidence
    def _store_source(
        self,
        cand: CandidateMovie,
        url: str,
        source_type: str,
        publisher: str | None,
        snippet: str,
        signals: list[Signal],
        query: str | None = None,
        reliability: float = 0.5,
        title: str | None = None,
    ) -> None:
        self.repos.candidates.add_source(
            cand,
            url=url,
            domain=domain_of(url) if "://" in url else url.split(":")[0],
            publisher=publisher,
            source_type=source_type,
            title=title,
            snippet=truncate(snippet, 500),
            query=query,
            reliability=reliability,
            signals=[s.as_dict() for s in signals[:60]],
        )

    def _summary(self, cand: CandidateMovie) -> EvidenceSummary:
        inputs = []
        for src in self.repos.candidates.sources(cand):
            if src.source_type in ("metadata", "ratings"):
                continue
            sigs = [
                Signal(s["field"], s["polarity"], s["phrase"], s["sentence"], s.get("flag"))
                for s in src.signals
            ]
            inputs.append(SourceInput(src.url, src.domain or src.url, src.source_type, src.reliability, sigs))
        return EvidenceSummary.from_sources(inputs)

    def _reference_vectors(self):
        positives = []
        for ref in self.repos.references.list(self.user):
            try:
                weight = Importance(ref.importance).weight
            except ValueError:
                weight = 0.55
            traits = self.repos.movies.traits(ref.movie_id)
            positives.append((ref.movie.label, traits, weight))
        negatives = []
        for fb in self.repos.feedback.latest_per_movie(self.user):
            if fb.rating_label in ("disliked", "medium", "average", "medium_low"):
                traits = self.repos.movies.traits(fb.movie_id)
                if len(traits) >= 3:
                    negatives.append((fb.movie.label, traits, 1.0))
        return positives, negatives

    def _cast_flags(self, movie: Movie) -> dict[str, str]:
        flags: dict[str, str] = {}
        for member in sorted(movie.cast or [], key=lambda c: c.get("order", 99))[:3]:
            prefs = self.repos.actors.for_actor(self.user, member.get("name", ""))
            if any(p.scope == "universal" and p.sentiment < 0 for p in prefs):
                flags["potential_cast_mismatch"] = STRONG
            elif len({p.movie_id for p in prefs if p.sentiment < 0}) >= 2:
                flags.setdefault("potential_cast_mismatch", MODERATE)
        return flags

    # ------------------------------------------------------------------ outcomes
    def _finish(self, cand: CandidateMovie, status: ResearchStatus, reason: str) -> PipelineResult:
        cand.research_status = status.value
        cand.decision_reason = reason
        cand.research_version = RESEARCH_VERSION
        cand.evaluated_at = utcnow()
        self._log(cand, 13, f"decision: {status.value}", reason=reason)
        self.repos.session.flush()
        return PipelineResult(cand, status, reason)

    def _reject(self, cand: CandidateMovie, movie: Movie, reason: str) -> PipelineResult:
        self.repos.rejected.add(self.user, movie, reason, "research_pipeline", cand.confidence or "HIGH")
        return self._finish(cand, ResearchStatus.REJECTED, reason)


def _mentions_title(text: str, movie: Movie) -> bool:
    norm = f" {normalize_text(text)} "
    return f" {movie.normalized_title} " in norm


_STRENGTH_LABELS = {
    "opening": "strong_opening",
    "story_quality": "clear_story",
    "story_progression": "event_progression",
    "acting_cast": "strong_acting",
    "pacing_continuity": "continuous_events",
    "production": "strong_production",
    "tension_action": "strong_tension",
}


def _strengths(dims: dict[str, float | None], a) -> list[str]:
    out = []
    for dim, label in _STRENGTH_LABELS.items():
        v = dims.get(dim)
        if v is not None and v >= 0.68:
            if dim == "acting_cast" and (a.get("acting_quality") or 0) < 0.65:
                continue  # a famous cast is not evidence of good acting
            out.append(label)
    if a.franchise_dependency == "none":
        out.append("standalone")
    return out
