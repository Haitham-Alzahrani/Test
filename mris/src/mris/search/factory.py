"""Build the configured providers from settings."""

from __future__ import annotations

from dataclasses import dataclass

from mris.config import Settings, get_settings
from mris.search.base import MetadataProvider, PageFetcher, RatingsProvider, WebSearchProvider
from mris.search.tmdb import TMDbClient
from mris.search.web import BraveSearch, HttpPageFetcher, OMDbClient, TavilySearch


@dataclass
class Providers:
    metadata: MetadataProvider | None = None
    ratings: RatingsProvider | None = None
    web: WebSearchProvider | None = None
    fetcher: PageFetcher | None = None

    def describe(self) -> dict[str, str]:
        return {
            "metadata": getattr(self.metadata, "name", "not configured")
            if self.metadata
            else "not configured",
            "ratings": getattr(self.ratings, "name", "not configured") if self.ratings else "not configured",
            "web_search": getattr(self.web, "name", "not configured") if self.web else "not configured",
            "page_fetch": "enabled" if self.fetcher else "disabled",
        }


def build_providers(settings: Settings | None = None) -> Providers:
    s = settings or get_settings()
    providers = Providers()
    if s.tmdb_api_key:
        providers.metadata = TMDbClient(
            s.tmdb_api_key,
            timeout=s.http_timeout,
            min_vote_count=s.min_vote_count,
            max_pages=s.max_discovery_pages,
        )
    if s.omdb_api_key:
        providers.ratings = OMDbClient(s.omdb_api_key, timeout=s.http_timeout)
    if s.search_provider == "brave" and s.brave_api_key:
        providers.web = BraveSearch(s.brave_api_key, timeout=s.http_timeout)
    elif s.search_provider == "tavily" and s.tavily_api_key:
        providers.web = TavilySearch(s.tavily_api_key, timeout=s.http_timeout)
    if providers.web and s.fetch_pages:
        providers.fetcher = HttpPageFetcher(timeout=s.http_timeout)
    return providers
