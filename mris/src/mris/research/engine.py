"""Systematic, resumable search (sections 18-19).

Order: newest configured year first; inside a year January -> December; inside a month
theatrical -> streaming -> wide -> independent, then by release date.  The cursor (year, month,
last candidate, counters) is committed after every candidate, so "continue" / "اكمل" always
resumes at the exact next candidate - even after a crash or Ctrl+C.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from mris.config import Settings, get_settings
from mris.models import CandidateMovie, ResearchCursor, ResearchStatus, User
from mris.models.tables import utcnow
from mris.repositories import Repos
from mris.research.pipeline import ResearchPipeline
from mris.search.base import ProviderError
from mris.search.factory import Providers

MONTHS_EN = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


@dataclass
class RunResult:
    found: CandidateMovie | None = None
    evaluated: int = 0
    rejected: int = 0
    blocked: int = 0
    insufficient: int = 0
    exhausted: bool = False
    stopped_reason: str = ""
    position: str = ""
    months_scanned: list[str] = field(default_factory=list)


class ResearchEngine:
    def __init__(
        self,
        repos: Repos,
        user: User,
        providers: Providers,
        settings: Settings | None = None,
        commit: Callable[[], None] | None = None,
        today: date | None = None,
        pipeline: ResearchPipeline | None = None,
    ) -> None:
        self.repos = repos
        self.user = user
        self.providers = providers
        self.settings = settings or get_settings()
        self.pipeline = pipeline or ResearchPipeline(repos, user, providers, self.settings)
        self._commit = commit or repos.session.commit
        self.today = today or date.today()

    # ----------------------------------------------------------------- cursor
    def cursor(self) -> ResearchCursor:
        return self.repos.cursor.get_or_create(
            self.user, self.settings.search_start_year, self.settings.search_end_year
        )

    def position(self) -> str:
        c = self.cursor()
        return f"{MONTHS_EN[c.month - 1]} {c.year}"

    def jump_to(self, year: int, month: int = 1) -> ResearchCursor:
        c = self.cursor()
        if (c.year, c.month) != (year, month):
            c.year, c.month = year, month
            c.month_discovered = bool(self.repos.queue.for_period(year, month))
            c.last_queue_item_id = None
            c.last_candidate = None
        c.status = "active"
        c.range_end_year = min(c.range_end_year, year)
        self.repos.events.log("cursor", f"cursor moved to {MONTHS_EN[month - 1]} {year}")
        self._commit()
        return c

    def _advance(self, c: ResearchCursor) -> None:
        if c.month < 12:
            c.month += 1
        else:
            c.year -= 1
            c.month = 1
        c.month_discovered = bool(self.repos.queue.for_period(c.year, c.month))
        c.last_queue_item_id = None
        if c.year < c.range_end_year:
            c.status = "exhausted"
        self.repos.events.log("cursor", f"advanced to {MONTHS_EN[c.month - 1]} {c.year}", status=c.status)

    def _is_future(self, year: int, month: int) -> bool:
        return (year, month) > (self.today.year, self.today.month)

    # ----------------------------------------------------------------- discovery
    def discover(self, year: int, month: int) -> int:
        """Fill the queue for one month. Returns the number of new queue items."""
        if self.providers.metadata is None:
            raise RuntimeError("No discovery provider configured (set MRIS_TMDB_API_KEY).")
        found = self.providers.metadata.discover_month(year, month)
        added = 0
        for d in found:
            movie = self.repos.movies.by_tmdb(d.tmdb_id)
            if movie is None:
                movie, _ = self.repos.movies.get_or_create(
                    d.title, d.release_date.year if d.release_date else year
                )
                if movie.tmdb_id is None:
                    movie.tmdb_id = d.tmdb_id
            if movie.release_date is None:
                movie.release_date = d.release_date
            if movie.original_language is None:
                movie.original_language = d.original_language
            before = self.repos.queue.get(year, month, movie)
            category = "unknown"
            if before is None:
                # Details are needed for the release category (theatrical / streaming / ...) that
                # orders the month; they are cached so the pipeline does not fetch them twice.
                try:
                    meta = self.providers.metadata.details(d.tmdb_id)
                    self.pipeline.metadata_cache[d.tmdb_id] = meta
                    category = meta.release_category
                except ProviderError as exc:
                    self.repos.events.log("error", f"details failed for {d.title}: {exc}")
            item = self.repos.queue.add(year, month, movie, self.providers.metadata.name, category)
            if category != "unknown":
                item.release_category = category
            added += before is None
        self.repos.queue.reorder(year, month)
        self.repos.events.log("discovery", f"{MONTHS_EN[month - 1]} {year}: {len(found)} found, {added} new")
        return added

    # ----------------------------------------------------------------- main loop
    def continue_search(
        self,
        year: int | None = None,
        max_candidates: int | None = None,
        stop_on_first: bool = True,
        progress: Callable[[str], None] | None = None,
    ) -> RunResult:
        say = progress or (lambda _msg: None)
        c = self.cursor()
        if year is not None and c.year != year:
            self.jump_to(year, 1)
            c = self.cursor()
        budget = max_candidates or self.settings.max_candidates_per_run
        result = RunResult()

        while True:
            if c.status == "exhausted" or c.year < c.range_end_year:
                c.status = "exhausted"
                result.exhausted = True
                result.stopped_reason = "search range exhausted"
                break
            if self._is_future(c.year, c.month):
                self._advance(c)
                self._commit()
                continue

            label = f"{MONTHS_EN[c.month - 1]} {c.year}"
            if not c.month_discovered:
                if self.providers.metadata is None:
                    if self.repos.queue.pending(c.year, c.month):
                        c.month_discovered = True  # manually queued candidates only
                    else:
                        result.stopped_reason = (
                            "no discovery provider configured (MRIS_TMDB_API_KEY) and no manually queued "
                            f"candidates for {label}"
                        )
                        break
                else:
                    say(f"discovering {label} ...")
                    try:
                        self.discover(c.year, c.month)
                    except ProviderError as exc:
                        result.stopped_reason = f"discovery failed for {label}: {exc}"
                        self.repos.events.log("error", result.stopped_reason)
                        self._commit()
                        break
                    c.month_discovered = True
                    self._commit()
            if label not in result.months_scanned:
                result.months_scanned.append(label)

            pending = self.repos.queue.pending(c.year, c.month)
            for item in pending:
                if result.evaluated >= budget:
                    result.stopped_reason = f"per-run limit reached ({budget} candidates); cursor saved"
                    result.position = self.position()
                    self._commit()
                    return result
                say(f"researching {item.candidate} [{item.release_category}] ...")
                item.research_status = "in_progress"
                try:
                    outcome = self.pipeline.research(item.movie, item.discovery_source, item.release_category)
                    item.research_status = outcome.status.value
                    item.candidate_id = outcome.candidate.id
                    item.release_category = outcome.candidate.release_category
                    item.next_action = "show" if outcome.status == ResearchStatus.PASSED else None
                except ProviderError as exc:
                    item.research_status = ResearchStatus.ERROR.value
                    item.next_action = f"retry: {exc}"[:200]
                    self.repos.events.log("error", f"{item.candidate}: {exc}")
                    outcome = None
                item.last_checked = utcnow()
                c.last_queue_item_id = item.id
                c.last_candidate = item.candidate
                c.candidates_evaluated += 1
                result.evaluated += 1
                if outcome is not None:
                    if outcome.status == ResearchStatus.REJECTED:
                        c.candidates_rejected += 1
                        result.rejected += 1
                    elif outcome.status == ResearchStatus.BLOCKED:
                        result.blocked += 1
                    elif outcome.status == ResearchStatus.INSUFFICIENT_EVIDENCE:
                        result.insufficient += 1
                    elif outcome.status == ResearchStatus.PASSED:
                        c.candidates_passed += 1
                self._commit()  # every candidate is durable: "continue" resumes right after it
                if outcome is not None and outcome.status == ResearchStatus.PASSED and stop_on_first:
                    result.found = outcome.candidate
                    result.stopped_reason = "strong candidate found"
                    result.position = self.position()
                    return result

            self._advance(c)
            self._commit()

        result.position = self.position()
        self._commit()
        return result
