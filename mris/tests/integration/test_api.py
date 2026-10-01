import pytest
from fastapi.testclient import TestClient

from mris.api.app import create_app
from tests.fixtures.fake_providers import fake_providers


@pytest.fixture()
def client(engine, settings, monkeypatch):
    monkeypatch.setattr("mris.service.get_settings", lambda: settings)
    monkeypatch.setattr("mris.research.pipeline.get_settings", lambda: settings)
    monkeypatch.setattr("mris.research.engine.get_settings", lambda: settings)
    return TestClient(create_app(engine=engine, providers=fake_providers(), migrate=False))


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_movies_and_detail(client):
    movies = client.get("/movies", params={"q": "town"}).json()
    assert movies and movies[0]["title"] == "The Town"
    detail = client.get(f"/movies/{movies[0]['id']}").json()
    assert detail["feedback"]["rating"] == "excellent"
    assert client.get("/movies/999999").status_code == 404


def test_watchlist_roundtrip(client):
    assert client.post("/watchlist", json={"title": "Heat", "year": 2026}).status_code == 200
    titles = [e["movie"]["title"] for e in client.get("/watchlist").json()]
    assert "Heat" in titles and "Hotel Mumbai" in titles


def test_feedback_structured_and_natural(client):
    r = client.post("/feedback", json={"title": "Plane", "year": 2023, "rating": "liked"})
    assert r.status_code == 200 and r.json()["movie"] == "Plane (2023)"
    r = client.post("/feedback", json={"text": "The Amateur بطيء جدا"})
    assert r.json()["rating"] == "disliked"
    assert client.post("/feedback", json={"title": "X", "rating": "great!!"}).status_code == 422


def test_research_continue_and_recommendations(client):
    r = client.post("/research/continue", json={}).json()
    assert r["found"] == "Iron Tide (2026)"
    assert "Quiet Harbor" not in r["message"]
    status = client.get("/research/status").json()
    assert status["cursor"]["passed"] == 1
    # already shown once -> not repeated
    assert client.get("/recommendations").json()["recommendations"] == []


def test_preferences(client):
    prefs = client.get("/preferences").json()
    assert prefs["rules"]["weight"]["opening"]["value"] == 20
    assert prefs["rules"]["exclusion"]["science_fiction"]["enabled"] is True


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/ui/movies",
        "/ui/watchlist",
        "/ui/rejected",
        "/ui/references",
        "/ui/preferences",
        "/ui/research",
        "/ui/history",
    ],
)
def test_dashboard_pages_render(client, path):
    r = client.get(path)
    assert r.status_code == 200 and "MRIS" in r.text


def test_dashboard_message_form(client):
    r = client.post("/ui/message", data={"text": "ضعه للمشاهدة لاحقًا"}, follow_redirects=True)
    assert r.status_code == 200
