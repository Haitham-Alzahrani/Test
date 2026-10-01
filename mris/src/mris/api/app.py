"""FastAPI application: JSON API + local web dashboard (server-rendered, no JS build)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from mris import __version__
from mris.database import get_engine, make_session_factory, upgrade_database
from mris.models import Movie, RatingLabel, RuleType
from mris.search.factory import Providers
from mris.service import MRIS

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class FeedbackIn(BaseModel):
    title: str | None = Field(None, description="Movie title (omit to use `text` only)")
    year: int | None = None
    rating: str | None = Field(
        None, description="loved|excellent|liked|good|medium|average|medium_low|disliked"
    )
    notes: str | None = None
    text: str | None = Field(None, description="Free natural-language feedback (Arabic or English)")
    positive: list[str] = []
    negative: list[str] = []


class WatchlistIn(BaseModel):
    title: str
    year: int | None = None
    note: str | None = None


class ContinueIn(BaseModel):
    year: int | None = None
    month: int | None = Field(None, ge=1, le=12)
    max_candidates: int | None = Field(None, ge=1, le=500)


class MessageIn(BaseModel):
    text: str


def movie_dict(m: Movie) -> dict[str, Any]:
    return {
        "id": m.id,
        "title": m.title,
        "year": m.year,
        "media_type": m.media_type,
        "release_date": m.release_date.isoformat() if m.release_date else None,
        "language": m.original_language,
        "genres": m.genres,
        "runtime": m.runtime,
        "director": m.director,
        "cast": [c.get("name") for c in (m.cast or [])[:5]],
        "tmdb_id": m.tmdb_id,
        "imdb_id": m.imdb_id,
        "ratings": m.ratings,
        "metadata_verified": m.metadata_verified,
    }


def create_app(
    engine: Engine | None = None, providers: Providers | None = None, migrate: bool = True
) -> FastAPI:
    if migrate and engine is None:
        upgrade_database()
    engine = engine or get_engine()
    factory = make_session_factory(engine)
    app = FastAPI(title="MRIS", version=__version__, description="Movie Recommendation Intelligence System")

    def get_service() -> Iterator[MRIS]:
        session = factory()
        try:
            svc = MRIS(session, providers=providers)
            try:
                svc.user  # noqa: B018
            except LookupError:
                svc.init()
            yield svc
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------ JSON API
    @app.get("/health")
    def health() -> dict[str, Any]:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return {"status": "ok", "version": __version__}

    @app.get("/movies")
    def movies(
        q: str | None = None,
        limit: int = Query(100, le=1000),
        offset: int = 0,
        svc: MRIS = Depends(get_service),
    ) -> list[dict[str, Any]]:
        return [movie_dict(m) for m in svc.repos.movies.list(limit, offset, q)]

    @app.get("/movies/{movie_id}")
    def movie(movie_id: int, svc: MRIS = Depends(get_service)) -> dict[str, Any]:
        m = svc.repos.movies.get(movie_id)
        if m is None:
            raise HTTPException(404, "movie not found")
        user = svc.user
        fb = svc.repos.feedback.latest(user, m)
        cand = svc.repos.candidates.for_movie(m)
        rejected = svc.repos.rejected.get(user, m)
        return {
            **movie_dict(m),
            "traits": svc.repos.movies.traits(m.id),
            "feedback": {
                "rating": fb.rating_label,
                "status": fb.status,
                "positive": fb.positive_traits,
                "negative": fb.negative_traits,
                "notes": fb.reason_text,
            }
            if fb
            else None,
            "candidate": {
                "status": cand.research_status,
                "confidence": cand.confidence,
                "decision": cand.decision_reason,
                "strengths": cand.strengths,
                "risks": cand.risks,
            }
            if cand
            else None,
            # the client asked for this specific movie, so a rejection may be discussed
            "rejected": {"reason": rejected.rejection_reason, "source": rejected.source_of_rejection}
            if rejected
            else None,
        }

    @app.get("/recommendations")
    def recommendations(
        count: int = Query(1, ge=1, le=10),
        research: bool = False,
        score: bool = False,
        svc: MRIS = Depends(get_service),
    ) -> dict[str, Any]:
        recs = svc.recommend(count, research=research, show_score=score)
        items = []
        for r in recs:
            item = {
                "title": r.candidate.movie.title,
                "year": r.candidate.movie.year,
                "text": r.text,
                "confidence": r.candidate.confidence,
                "strengths": r.candidate.strengths,
                "recommendation_id": r.history.id,
            }
            if score:
                item["score"] = r.candidate.total_score
            items.append(item)
        return {"recommendations": items, "position": svc.engine().position()}

    @app.post("/feedback")
    def post_feedback(body: FeedbackIn, svc: MRIS = Depends(get_service)) -> dict[str, Any]:
        if body.title and body.rating:
            try:
                RatingLabel(body.rating)
            except ValueError as exc:
                raise HTTPException(422, f"invalid rating '{body.rating}'") from exc
            report = svc.feedback(
                body.title, body.rating, body.year, body.notes, body.positive, body.negative
            )
            return {"movie": report.movie, "changes": report.changes}
        text = body.text or " ".join(filter(None, [body.title, body.notes]))
        if not text:
            raise HTTPException(422, "provide title+rating or text")
        reply = svc.handle_message(text)
        return {"reply": reply.text, **reply.data}

    @app.post("/watchlist")
    def post_watchlist(body: WatchlistIn, svc: MRIS = Depends(get_service)) -> dict[str, Any]:
        m = svc.watchlist_add(body.title, body.year, body.note)
        return {"added": m.label, "movie_id": m.id}

    @app.get("/watchlist")
    def get_watchlist(svc: MRIS = Depends(get_service)) -> list[dict[str, Any]]:
        return [
            {"movie": movie_dict(e.movie), "note": e.note, "added_at": e.added_at.isoformat()}
            for e in svc.repos.watchlist.list(svc.user)
        ]

    @app.get("/preferences")
    def preferences(svc: MRIS = Depends(get_service)) -> dict[str, Any]:
        user = svc.user
        grouped: dict[str, dict[str, Any]] = {}
        for r in svc.repos.preferences.list(user):
            grouped.setdefault(r.rule_type, {})[r.key] = {
                "value": r.value,
                "enabled": r.enabled,
                "source": r.source,
            }
        return {
            "user": user.name,
            "response_language": user.response_language,
            "profile": user.profile,
            "rules": grouped,
        }

    @app.get("/research/status")
    def research_status(svc: MRIS = Depends(get_service)) -> dict[str, Any]:
        return svc.status()

    @app.post("/research/continue")
    def research_continue(body: ContinueIn | None = None, svc: MRIS = Depends(get_service)) -> dict[str, Any]:
        body = body or ContinueIn()
        result, rec, text = svc.continue_search(body.year, body.month, body.max_candidates)
        return {
            "message": text,
            "found": rec.candidate.movie.label if rec else None,
            "evaluated": result.evaluated,
            "rejected": result.rejected,
            "exhausted": result.exhausted,
            "stopped_reason": result.stopped_reason,
            "position": svc.engine().position(),
            "months_scanned": result.months_scanned,
        }

    @app.post("/message")
    def message(body: MessageIn, svc: MRIS = Depends(get_service)) -> dict[str, Any]:
        reply = svc.handle_message(body.text)
        return {"reply": reply.text, **reply.data}

    # ------------------------------------------------------------------ web dashboard
    def page(request: Request, name: str, **ctx: Any) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, name, {"active": name.removesuffix(".html"), **ctx})

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, reply: str | None = None, svc: MRIS = Depends(get_service)):
        status = svc.status()
        last = svc.repos.recommendations.latest(svc.user)
        return page(request, "dashboard.html", s=status, last=last, reply=reply)

    @app.post("/ui/message")
    def ui_message(text: str = Form(...), svc: MRIS = Depends(get_service)):
        reply = svc.handle_message(text)
        from urllib.parse import quote

        return RedirectResponse(f"/?reply={quote(reply.text)}", status_code=303)

    @app.get("/ui/movies", response_class=HTMLResponse)
    def ui_movies(request: Request, q: str | None = None, svc: MRIS = Depends(get_service)):
        user = svc.user
        rows = []
        for fb in svc.repos.feedback.latest_per_movie(user):
            rows.append(fb)
        rows.sort(key=lambda f: f.created_at, reverse=True)
        if q:
            rows = [f for f in rows if q.lower() in f.movie.title.lower()]
        return page(request, "movies.html", rows=rows, q=q or "")

    @app.get("/ui/watchlist", response_class=HTMLResponse)
    def ui_watchlist(request: Request, svc: MRIS = Depends(get_service)):
        return page(request, "watchlist.html", rows=svc.repos.watchlist.list(svc.user))

    @app.post("/ui/watchlist")
    def ui_watchlist_add(
        title: str = Form(...), year: str = Form(""), note: str = Form(""), svc: MRIS = Depends(get_service)
    ):
        svc.watchlist_add(title, int(year) if year.strip().isdigit() else None, note or None)
        return RedirectResponse("/ui/watchlist", status_code=303)

    @app.get("/ui/rejected", response_class=HTMLResponse)
    def ui_rejected(request: Request, svc: MRIS = Depends(get_service)):
        return page(request, "rejected.html", rows=svc.repos.rejected.list(svc.user))

    @app.get("/ui/references", response_class=HTMLResponse)
    def ui_references(request: Request, svc: MRIS = Depends(get_service)):
        refs = svc.repos.references.list(svc.user)
        rows = [(r, svc.repos.movies.traits(r.movie_id)) for r in refs]
        order = {"very_high": 0, "high": 1, "medium": 2, "low": 3}
        rows.sort(key=lambda x: (order.get(x[0].importance, 9), x[0].movie.title))
        return page(request, "references.html", rows=rows)

    @app.get("/ui/preferences", response_class=HTMLResponse)
    def ui_preferences(request: Request, svc: MRIS = Depends(get_service)):
        user = svc.user
        rules = svc.repos.preferences.list(user)
        grouped: dict[str, list] = {}
        for r in rules:
            grouped.setdefault(r.rule_type, []).append(r)
        grouped.get(RuleType.TRAIT_AFFINITY.value, []).sort(key=lambda r: r.value, reverse=True)
        return page(
            request,
            "preferences.html",
            user=user,
            grouped=grouped,
            actors=svc.repos.actors.list(user),
            franchises=svc.repos.franchises.list(),
        )

    @app.get("/ui/research", response_class=HTMLResponse)
    def ui_research(request: Request, svc: MRIS = Depends(get_service)):
        return page(
            request,
            "research.html",
            s=svc.status(),
            queue=svc.repos.queue.list(None, 200),
            events=svc.repos.events.recent(40),
        )

    @app.post("/ui/research/continue")
    def ui_research_continue(svc: MRIS = Depends(get_service)):
        _, _, text = svc.continue_search(max_candidates=25)
        from urllib.parse import quote

        return RedirectResponse(f"/?reply={quote(text)}", status_code=303)

    @app.get("/ui/history", response_class=HTMLResponse)
    def ui_history(request: Request, svc: MRIS = Depends(get_service)):
        return page(request, "history.html", rows=svc.repos.recommendations.list(svc.user, 200))

    return app
