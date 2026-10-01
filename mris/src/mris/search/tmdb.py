"""The Movie Database (TMDb) client: monthly discovery and verified metadata."""

from __future__ import annotations

import calendar
from datetime import date

import httpx

from mris.search.base import (
    AudienceReview,
    CastMember,
    DiscoveredMovie,
    MovieMetadata,
    ProviderError,
)

API = "https://api.themoviedb.org/3"

# US release types: 1 premiere, 2 limited theatrical, 3 theatrical, 4 digital, 5 physical, 6 TV
_THEATRICAL, _LIMITED, _DIGITAL = 3, 2, 4


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


def classify_release(release_dates: dict, popularity: float | None = None) -> str:
    """theatrical (US wide), streaming (digital premiere), wide (wide theatrical outside the US
    only), independent (limited / festival only)."""
    by_country: dict[str, list[tuple[int, date | None]]] = {}
    for entry in release_dates.get("results", []):
        by_country[entry.get("iso_3166_1", "")] = [
            (r.get("type"), _parse_date(r.get("release_date"))) for r in entry.get("release_dates", [])
        ]
    us = by_country.get("US", [])
    us_types = {t for t, _ in us}
    if _THEATRICAL in us_types:
        theatrical = min((d for t, d in us if t == _THEATRICAL and d), default=None)
        digital = min((d for t, d in us if t == _DIGITAL and d), default=None)
        if digital and theatrical and digital < theatrical:
            return "streaming"
        return "theatrical"
    if _DIGITAL in us_types:
        return "streaming"
    if any(_THEATRICAL in {t for t, _ in rel} for rel in by_country.values()):
        return "wide"
    if _LIMITED in us_types or us:
        return "independent"
    return "unknown"


class TMDbClient:
    name = "tmdb"

    def __init__(
        self,
        api_key: str,
        timeout: float = 20.0,
        min_vote_count: int = 15,
        max_pages: int = 5,
        region: str = "US",
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("TMDb API key is required")
        self.min_vote_count = min_vote_count
        self.max_pages = max_pages
        self.region = region
        headers = {"Accept": "application/json"}
        self._params: dict[str, str] = {}
        if api_key.startswith("eyJ"):  # v4 read access token (JWT)
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            self._params["api_key"] = api_key
        self._http = client or httpx.Client(timeout=timeout, headers=headers)

    def _get(self, path: str, **params) -> dict:
        try:
            resp = self._http.get(f"{API}{path}", params={**self._params, **params})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"TMDb request failed for {path}: {exc}") from exc

    def discover_month(self, year: int, month: int) -> list[DiscoveredMovie]:
        last_day = calendar.monthrange(year, month)[1]
        end = min(date(year, month, last_day), date.today())
        start = date(year, month, 1)
        if start > end:
            return []
        found: dict[int, DiscoveredMovie] = {}
        for page in range(1, self.max_pages + 1):
            data = self._get(
                "/discover/movie",
                **{
                    "primary_release_date.gte": start.isoformat(),
                    "primary_release_date.lte": end.isoformat(),
                    "sort_by": "popularity.desc",
                    "include_adult": "false",
                    "include_video": "false",
                    "vote_count.gte": str(self.min_vote_count),
                    "with_runtime.gte": "75",
                    "page": str(page),
                },
            )
            for row in data.get("results", []):
                found[row["id"]] = DiscoveredMovie(
                    tmdb_id=row["id"],
                    title=row.get("title") or row.get("original_title") or "",
                    release_date=_parse_date(row.get("release_date")),
                    original_language=row.get("original_language"),
                    popularity=row.get("popularity"),
                    vote_count=row.get("vote_count"),
                )
            if page >= int(data.get("total_pages") or 1):
                break
        return sorted(found.values(), key=lambda d: (d.release_date or end, d.title))

    def search_title(self, title: str, year: int | None = None) -> list[DiscoveredMovie]:
        params = {"query": title, "include_adult": "false"}
        if year:
            params["primary_release_year"] = str(year)
        data = self._get("/search/movie", **params)
        return [
            DiscoveredMovie(
                tmdb_id=row["id"],
                title=row.get("title") or "",
                release_date=_parse_date(row.get("release_date")),
                original_language=row.get("original_language"),
                popularity=row.get("popularity"),
                vote_count=row.get("vote_count"),
            )
            for row in data.get("results", [])
        ]

    def details(self, tmdb_id: int) -> MovieMetadata:
        d = self._get(
            f"/movie/{tmdb_id}",
            append_to_response="credits,keywords,release_dates,videos,reviews,external_ids",
        )
        release = _parse_date(d.get("release_date"))
        crew = d.get("credits", {}).get("crew", [])
        directors = [c["name"] for c in crew if c.get("job") == "Director"]
        cast = [
            CastMember(
                name=c["name"],
                order=c.get("order", 99),
                popularity=c.get("popularity"),
                character=c.get("character"),
            )
            for c in sorted(d.get("credits", {}).get("cast", []), key=lambda c: c.get("order", 99))[:10]
        ]
        trailer = next(
            (
                f"https://www.youtube.com/watch?v={v['key']}"
                for v in d.get("videos", {}).get("results", [])
                if v.get("site") == "YouTube" and v.get("type") == "Trailer"
            ),
            None,
        )
        reviews = [
            AudienceReview(
                url=r.get("url") or f"https://www.themoviedb.org/review/{r.get('id')}",
                author=r.get("author"),
                content=r.get("content") or "",
                rating=(r.get("author_details") or {}).get("rating"),
            )
            for r in d.get("reviews", {}).get("results", [])
            if r.get("content")
        ]
        collection = d.get("belongs_to_collection") or None
        position = size = None
        if collection:
            try:
                parts = self._get(f"/collection/{collection['id']}").get("parts", [])
                parts = sorted((p for p in parts if p.get("release_date")), key=lambda p: p["release_date"])
                size = len(parts)
                position = next((i + 1 for i, p in enumerate(parts) if p["id"] == tmdb_id), None)
            except ProviderError:
                pass
        return MovieMetadata(
            title=d.get("title") or d.get("original_title") or "",
            original_title=d.get("original_title"),
            year=release.year if release else None,
            tmdb_id=d["id"],
            imdb_id=d.get("imdb_id") or d.get("external_ids", {}).get("imdb_id"),
            release_date=release,
            original_language=d.get("original_language"),
            spoken_languages=[lang.get("iso_639_1") for lang in d.get("spoken_languages", [])],
            countries=[c.get("iso_3166_1") for c in d.get("production_countries", [])],
            genres=[g["name"] for g in d.get("genres", [])],
            keywords=[k["name"] for k in d.get("keywords", {}).get("keywords", [])],
            runtime=d.get("runtime") or None,
            director=", ".join(directors) or None,
            cast=cast,
            overview=d.get("overview") or None,
            collection_name=collection.get("name") if collection else None,
            collection_position=position,
            collection_size=size,
            budget=d.get("budget") or None,
            production_companies=[c["name"] for c in d.get("production_companies", [])],
            trailer_url=trailer,
            release_category=classify_release(d.get("release_dates", {}), d.get("popularity")),
            vote_average=d.get("vote_average"),
            vote_count=d.get("vote_count"),
            popularity=d.get("popularity"),
            audience_reviews=reviews,
            source_url=f"https://www.themoviedb.org/movie/{d['id']}",
        )
