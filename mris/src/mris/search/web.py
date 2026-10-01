"""Ratings (OMDb), web search (Brave / Tavily) and review page fetching."""

from __future__ import annotations

import html
import re

import httpx

from mris.search.base import ProviderError, Ratings, SearchResult

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) MRIS/1.0 (personal movie research)"


class OMDbClient:
    name = "omdb"

    def __init__(self, api_key: str, timeout: float = 20.0, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise ValueError("OMDb API key is required")
        self.api_key = api_key
        self._http = client or httpx.Client(timeout=timeout)

    def ratings(self, imdb_id: str | None, title: str, year: int | None) -> Ratings | None:
        params = {"apikey": self.api_key}
        if imdb_id:
            params["i"] = imdb_id
        else:
            params["t"] = title
            if year:
                params["y"] = str(year)
        try:
            resp = self._http.get("https://www.omdbapi.com/", params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"OMDb request failed: {exc}") from exc
        if data.get("Response") != "True":
            return None
        ratings = Ratings(source_url=f"https://www.imdb.com/title/{data.get('imdbID')}/")
        try:
            ratings.imdb = float(data["imdbRating"])
        except (KeyError, ValueError):
            pass
        try:
            ratings.imdb_votes = int(str(data.get("imdbVotes", "")).replace(",", ""))
        except ValueError:
            pass
        for item in data.get("Ratings", []):
            value = item.get("Value", "")
            if item.get("Source") == "Rotten Tomatoes" and value.endswith("%"):
                ratings.rotten_tomatoes = int(value.rstrip("%"))
            elif item.get("Source") == "Metacritic" and "/" in value:
                ratings.metacritic = int(value.split("/")[0])
        return ratings


class BraveSearch:
    name = "brave"

    def __init__(self, api_key: str, timeout: float = 20.0, client: httpx.Client | None = None) -> None:
        self._http = client or httpx.Client(
            timeout=timeout, headers={"X-Subscription-Token": api_key, "Accept": "application/json"}
        )

    def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        try:
            resp = self._http.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": str(max_results), "extra_snippets": "true"},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Brave search failed: {exc}") from exc
        results = []
        for row in data.get("web", {}).get("results", [])[:max_results]:
            snippet = " ".join([row.get("description", "")] + row.get("extra_snippets", []))
            results.append(
                SearchResult(
                    url=row["url"], title=_clean(row.get("title", "")), snippet=_clean(snippet), query=query
                )
            )
        return results


class TavilySearch:
    name = "tavily"

    def __init__(self, api_key: str, timeout: float = 30.0, client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self._http = client or httpx.Client(timeout=timeout, headers={"Authorization": f"Bearer {api_key}"})

    def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        try:
            resp = self._http.post(
                "https://api.tavily.com/search",
                json={"query": query, "max_results": max_results, "search_depth": "advanced"},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Tavily search failed: {exc}") from exc
        return [
            SearchResult(
                url=r["url"], title=r.get("title", ""), snippet=_clean(r.get("content", "")), query=query
            )
            for r in data.get("results", [])[:max_results]
        ]


_DROP_BLOCKS = re.compile(
    r"<(script|style|noscript|nav|footer|header|aside|form|svg)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)
_TAGS = re.compile(r"<[^>]+>")


def html_to_text(raw: str) -> str:
    raw = _DROP_BLOCKS.sub(" ", raw)
    raw = re.sub(r"</(p|div|li|h\d|br)>", ".\n", raw, flags=re.IGNORECASE)
    return _clean(html.unescape(_TAGS.sub(" ", raw)))


def _clean(text: str) -> str:
    text = _TAGS.sub(" ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


class HttpPageFetcher:
    """Downloads a review page and returns its readable text (best effort, never raises)."""

    MAX_BYTES = 600_000

    def __init__(self, timeout: float = 20.0, client: httpx.Client | None = None) -> None:
        self._http = client or httpx.Client(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )

    def fetch_text(self, url: str) -> str | None:
        try:
            resp = self._http.get(url)
            if resp.status_code != 200 or "html" not in resp.headers.get("content-type", ""):
                return None
            return html_to_text(resp.text[: self.MAX_BYTES])[:60_000]
        except httpx.HTTPError:
            return None
