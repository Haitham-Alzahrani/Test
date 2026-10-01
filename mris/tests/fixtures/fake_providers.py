"""Offline, deterministic providers used by the test-suite.

The review snippets below are synthetic test fixtures written for these tests; they are not
quotes from real publications.
"""

from __future__ import annotations

from datetime import date

from mris.search.base import CastMember, DiscoveredMovie, MovieMetadata, ProviderError, SearchResult
from mris.search.factory import Providers

STAR = 30.0
UNKNOWN = 0.8


def _meta(tmdb_id, title, rel, **kw) -> MovieMetadata:
    defaults = dict(
        original_language="en",
        countries=["US"],
        genres=["Action", "Thriller"],
        keywords=[],
        runtime=110,
        director="Some Director",
        cast=[
            CastMember("Lead Star", 0, STAR),
            CastMember("Second Star", 1, 18.0),
            CastMember("Support", 2, 6.0),
        ],
        overview="",
        budget=70_000_000,
        release_category="theatrical",
        vote_average=7.2,
        vote_count=900,
    )
    defaults.update(kw)
    return MovieMetadata(
        title=title,
        year=rel.year,
        tmdb_id=tmdb_id,
        release_date=rel,
        imdb_id=f"tt{tmdb_id:07d}",
        source_url=f"https://www.themoviedb.org/movie/{tmdb_id}",
        **defaults,
    )


MOVIES: dict[int, MovieMetadata] = {
    # January 2026
    101: _meta(
        101,
        "Star Rift",
        date(2026, 1, 9),
        genres=["Science Fiction", "Action"],
        overview="Aliens invade a space station.",
    ),
    102: _meta(102, "Mutiny", date(2026, 1, 16), overview="A crew fights back after a heist goes wrong."),
    103: _meta(
        103,
        "Quiet Harbor",
        date(2026, 1, 23),
        overview="A detective investigates a robbery.",
        keywords=["police"],
    ),
    104: _meta(
        104,
        "Seoul Night",
        date(2026, 1, 30),
        original_language="ko",
        countries=["KR"],
        overview="A cop chases a gang.",
    ),
    # February 2026
    201: _meta(
        201,
        "Iron Tide",
        date(2026, 2, 6),
        overview="Saturation divers race against time to rescue a trapped crew on an offshore oil rig "
        "after an explosion.",
    ),
    202: _meta(
        202,
        "Last Run",
        date(2026, 2, 20),
        overview="A getaway driver is pursued by a cartel.",
        release_category="streaming",
    ),
    # reference movie (not in discovery) - used by reference enrichment
    900: _meta(
        900,
        "Nobody",
        date(2021, 3, 26),
        overview="A mild-mannered father becomes the target of a vengeful drug lord after a home robbery.",
    ),
    # March 2026
    301: _meta(
        301,
        "Wick Legacy",
        date(2026, 3, 6),
        collection_name="Wick Collection",
        collection_position=4,
        overview="An assassin returns.",
    ),
}

DISCOVERY: dict[tuple[int, int], list[int]] = {
    (2026, 1): [101, 102, 103, 104],
    (2026, 2): [201, 202],
    (2026, 3): [301],
}

REVIEWS: dict[str, list[tuple[str, str]]] = {
    "Quiet Harbor": [
        (
            "https://variety.com/quiet-harbor-review",
            "Quiet Harbor review: a slow start and a lengthy setup; "
            "it takes 40 minutes before anything happens. Strong performances though.",
        ),
        (
            "https://www.reddit.com/r/movies/quiet_harbor",
            "Quiet Harbor discussion: the first act is slow and the movie is talky. Slow-burn thriller.",
        ),
        (
            "https://www.theguardian.com/quiet-harbor",
            "Quiet Harbor is a slow-burn drama with a sluggish opening.",
        ),
    ],
    "Iron Tide": [
        (
            "https://variety.com/iron-tide-review",
            "Iron Tide review: the film wastes no time and hits the ground "
            "running. A tense, taut survival thriller with strong performances and a clear story.",
        ),
        (
            "https://www.hollywoodreporter.com/iron-tide",
            "Iron Tide is gripping from the start, tightly plotted and "
            "relentless. Excellent action set pieces, slick production values are high, "
            "and it never lets up.",
        ),
        (
            "https://www.reddit.com/r/movies/iron_tide",
            "Iron Tide discussion: fast-paced, edge-of-your-seat, "
            "you can follow what's happening in the action. Constant tension, well-plotted, "
            "believable characters.",
        ),
        (
            "https://www.imdb.com/title/tt0000201/reviews",
            "Iron Tide: hooks you immediately, great acting, "
            "realistic and keeps escalating. Stunning cinematography.",
        ),
    ],
    "Last Run": [
        ("https://www.imdb.com/title/tt0000202/reviews", "Last Run: fun chase movie."),
    ],
    "Wick Legacy": [
        (
            "https://variety.com/wick-legacy",
            "Wick Legacy: you need to have seen the previous films; set in the "
            "Wick universe. Thrilling action.",
        ),
    ],
}


class FakeMetadata:
    name = "fake-tmdb"

    def __init__(self, movies=None, discovery=None, fail_on: set[int] | None = None) -> None:
        self.movies = movies or MOVIES
        self.discovery = discovery or DISCOVERY
        self.fail_on = fail_on or set()
        self.detail_calls: list[int] = []

    def discover_month(self, year: int, month: int) -> list[DiscoveredMovie]:
        return [
            DiscoveredMovie(i, self.movies[i].title, self.movies[i].release_date, "en", 10.0, 100)
            for i in self.discovery.get((year, month), [])
        ]

    def search_title(self, title: str, year: int | None = None) -> list[DiscoveredMovie]:
        return [
            DiscoveredMovie(m.tmdb_id, m.title, m.release_date)
            for m in self.movies.values()
            if m.title.lower() == title.lower() and (year is None or m.year == year)
        ]

    def details(self, tmdb_id: int) -> MovieMetadata:
        self.detail_calls.append(tmdb_id)
        if tmdb_id in self.fail_on:
            raise ProviderError("boom")
        return self.movies[tmdb_id]


class FakeWeb:
    name = "fake-web"

    def __init__(self, reviews=None) -> None:
        self.reviews = reviews or REVIEWS
        self.queries: list[str] = []

    def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        self.queries.append(query)
        for title, items in self.reviews.items():
            if f'"{title}"' in query:
                return [
                    SearchResult(url=u, title=f"{title} review", snippet=s, query=query) for u, s in items
                ]
        return []


def fake_providers(web: bool = True) -> Providers:
    return Providers(metadata=FakeMetadata(), web=FakeWeb() if web else None)
