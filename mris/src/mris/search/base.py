"""Provider interfaces and the plain data they return.

Providers only *report* what external services say. They never fill gaps with guesses: a
field the service did not return stays ``None``/empty and the scoring layer treats it as
unknown (which lowers confidence instead of inventing a value).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass
class CastMember:
    name: str
    order: int = 99
    popularity: float | None = None
    character: str | None = None


@dataclass
class AudienceReview:
    url: str
    author: str | None
    content: str
    rating: float | None = None  # out of 10 when present


@dataclass
class DiscoveredMovie:
    tmdb_id: int
    title: str
    release_date: date | None
    original_language: str | None = None
    popularity: float | None = None
    vote_count: int | None = None


@dataclass
class MovieMetadata:
    title: str
    year: int | None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    original_title: str | None = None
    release_date: date | None = None
    original_language: str | None = None
    spoken_languages: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    runtime: int | None = None
    director: str | None = None
    cast: list[CastMember] = field(default_factory=list)
    overview: str | None = None
    collection_name: str | None = None
    collection_position: int | None = None
    collection_size: int | None = None
    budget: int | None = None
    production_companies: list[str] = field(default_factory=list)
    trailer_url: str | None = None
    release_category: str = "unknown"
    vote_average: float | None = None
    vote_count: int | None = None
    popularity: float | None = None
    audience_reviews: list[AudienceReview] = field(default_factory=list)
    source_url: str | None = None

    def missing_core_fields(self) -> list[str]:
        required = {
            "title": self.title,
            "year": self.year,
            "release_date": self.release_date,
            "original_language": self.original_language,
            "countries": self.countries,
            "genres": self.genres,
            "runtime": self.runtime,
            "cast": self.cast,
            "director": self.director,
        }
        return [k for k, v in required.items() if not v]


@dataclass
class Ratings:
    imdb: float | None = None
    imdb_votes: int | None = None
    rotten_tomatoes: int | None = None
    metacritic: int | None = None
    source_url: str | None = None

    def as_dict(self) -> dict[str, float | int]:
        data = {
            "imdb": self.imdb,
            "imdb_votes": self.imdb_votes,
            "rotten_tomatoes": self.rotten_tomatoes,
            "metacritic": self.metacritic,
        }
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    query: str
    content: str | None = None  # full text when the provider or page fetcher supplied it


class MetadataProvider(Protocol):
    name: str

    def discover_month(self, year: int, month: int) -> list[DiscoveredMovie]: ...

    def search_title(self, title: str, year: int | None = None) -> list[DiscoveredMovie]: ...

    def details(self, tmdb_id: int) -> MovieMetadata: ...


class RatingsProvider(Protocol):
    name: str

    def ratings(self, imdb_id: str | None, title: str, year: int | None) -> Ratings | None: ...


class WebSearchProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int = 8) -> list[SearchResult]: ...


class PageFetcher(Protocol):
    def fetch_text(self, url: str) -> str | None: ...


class ProviderError(RuntimeError):
    """Raised when an external service fails; research records it instead of guessing."""
