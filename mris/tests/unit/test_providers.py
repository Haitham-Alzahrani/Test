"""Real provider clients against mocked HTTP responses (no network)."""

import httpx

from mris.search.tmdb import TMDbClient, classify_release
from mris.search.web import BraveSearch, OMDbClient, html_to_text

DETAILS = {
    "id": 55,
    "title": "Deep Rig",
    "original_title": "Deep Rig",
    "release_date": "2026-02-06",
    "imdb_id": "tt1234567",
    "original_language": "en",
    "spoken_languages": [{"iso_639_1": "en"}],
    "production_countries": [{"iso_3166_1": "US"}],
    "genres": [{"id": 28, "name": "Action"}, {"id": 53, "name": "Thriller"}],
    "runtime": 104,
    "budget": 80000000,
    "overview": "Divers race against time.",
    "production_companies": [{"name": "Big Studio"}],
    "belongs_to_collection": {"id": 9, "name": "Deep Rig Collection"},
    "vote_average": 7.4,
    "vote_count": 1200,
    "popularity": 50.0,
    "credits": {
        "cast": [{"name": "Lead", "order": 0, "popularity": 25.0, "character": "Diver"}],
        "crew": [{"name": "Dir", "job": "Director"}],
    },
    "keywords": {"keywords": [{"name": "oil rig"}]},
    "release_dates": {
        "results": [{"iso_3166_1": "US", "release_dates": [{"type": 3, "release_date": "2026-02-06"}]}]
    },
    "videos": {"results": [{"site": "YouTube", "type": "Trailer", "key": "abc"}]},
    "reviews": {
        "results": [{"id": "r1", "author": "u", "content": "Hooks you immediately.", "author_details": {}}]
    },
}
COLLECTION = {"parts": [{"id": 55, "release_date": "2026-02-06"}]}


def tmdb_client():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/movie/55"):
            return httpx.Response(200, json=DETAILS)
        if request.url.path.endswith("/collection/9"):
            return httpx.Response(200, json=COLLECTION)
        if request.url.path.endswith("/discover/movie"):
            assert request.url.params["primary_release_date.gte"] == "2026-02-01"
            return httpx.Response(
                200,
                json={
                    "total_pages": 1,
                    "results": [{"id": 55, "title": "Deep Rig", "release_date": "2026-02-06"}],
                },
            )
        return httpx.Response(404)

    return TMDbClient("key", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_tmdb_details_parsing():
    meta = tmdb_client().details(55)
    assert meta.title == "Deep Rig" and meta.year == 2026 and meta.director == "Dir"
    assert meta.genres == ["Action", "Thriller"] and meta.runtime == 104
    assert meta.release_category == "theatrical"
    assert meta.collection_position == 1  # first film of its collection -> not a sequel
    assert meta.trailer_url.endswith("abc")
    assert meta.audience_reviews[0].content == "Hooks you immediately."
    assert meta.missing_core_fields() == []


def test_tmdb_discover():
    found = tmdb_client().discover_month(2026, 2)
    assert [d.title for d in found] == ["Deep Rig"]


def test_release_classification():
    def rel(*entries):
        return {
            "results": [
                {"iso_3166_1": c, "release_dates": [{"type": t, "release_date": d}]} for c, t, d in entries
            ]
        }

    assert classify_release(rel(("US", 4, "2026-01-01"))) == "streaming"
    assert classify_release(rel(("GB", 3, "2026-01-01"))) == "wide"
    assert classify_release(rel(("US", 2, "2026-01-01"))) == "independent"


def test_omdb_ratings():
    payload = {
        "Response": "True",
        "imdbID": "tt1",
        "imdbRating": "7.1",
        "imdbVotes": "12,345",
        "Ratings": [
            {"Source": "Rotten Tomatoes", "Value": "81%"},
            {"Source": "Metacritic", "Value": "64/100"},
        ],
    }
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    r = OMDbClient("k", client=client).ratings("tt1", "X", 2026)
    assert (r.imdb, r.imdb_votes, r.rotten_tomatoes, r.metacritic) == (7.1, 12345, 81, 64)


def test_brave_search_parsing():
    payload = {
        "web": {
            "results": [{"url": "https://variety.com/x", "title": "<b>X</b> review", "description": "Taut."}]
        }
    }
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    res = BraveSearch("k", client=client).search('"X" review')
    assert res[0].title == "X review" and res[0].snippet == "Taut."


def test_html_to_text_drops_scripts():
    text = html_to_text("<html><script>var a=1</script><p>Wastes no time.</p><nav>menu</nav></html>")
    assert "Wastes no time" in text and "var a" not in text and "menu" not in text
