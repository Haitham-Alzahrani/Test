"""`mris` command-line interface."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from mris import __version__
from mris.config import get_settings
from mris.database import (
    backup_database,
    current_revision,
    get_engine,
    make_session_factory,
    upgrade_database,
)
from mris.models import RuleType
from mris.service import MRIS

console = Console()
app = typer.Typer(help="Movie Recommendation Intelligence System", no_args_is_help=True, add_completion=False)
watchlist_app = typer.Typer(help="Watch-later list", no_args_is_help=True)
rejected_app = typer.Typer(help="Rejected titles (only shown on explicit request)", no_args_is_help=True)
profile_app = typer.Typer(
    help="User profile and taste rules", no_args_is_help=False, invoke_without_command=True
)
database_app = typer.Typer(help="Database maintenance", no_args_is_help=True)
research_app = typer.Typer(help="Research queue, evidence and diagnostics", no_args_is_help=True)
app.add_typer(watchlist_app, name="watchlist")
app.add_typer(rejected_app, name="rejected")
app.add_typer(profile_app, name="profile")
app.add_typer(database_app, name="database")
app.add_typer(research_app, name="research")

YearOpt = Annotated[int | None, typer.Option("--year", "-y", help="Release year")]


@contextmanager
def service(require_user: bool = True) -> Iterator[MRIS]:
    upgrade_database()
    session = make_session_factory(get_engine())()
    try:
        svc = MRIS(session)
        if require_user:
            try:
                svc.user  # noqa: B018 - validates that `mris init` ran
            except LookupError:
                console.print("[red]No profile yet. Run `mris init` first.[/red]")
                raise typer.Exit(1) from None
        yield svc
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _progress(msg: str) -> None:
    console.print(f"[dim]· {msg}[/dim]")


def _split(values: str | None) -> list[str]:
    return [v.strip() for v in (values or "").split(",") if v.strip()]


# --------------------------------------------------------------------------- core commands
@app.command()
def version() -> None:
    """Show the version."""
    console.print(f"mris {__version__}")


@app.command()
def init() -> None:
    """Create/upgrade the database and load the initial taste profile (idempotent)."""
    with service(require_user=False) as svc:
        user, created = svc.init()
    console.print(f"[green]Database ready:[/green] {get_settings().database_file}")
    console.print(("Seeded initial profile for " if created else "Profile already present: ") + user.name)


@app.command()
def status() -> None:
    """Counts, research cursor and configured providers."""
    with service() as svc:
        s = svc.status()
    t = Table(title=f"MRIS — {s['user']}", show_header=False)
    for key in (
        "watched",
        "loved",
        "liked",
        "medium",
        "disliked",
        "watchlist",
        "rejected",
        "references",
        "recommendations",
        "movies",
    ):
        t.add_row(key, str(s[key]))
    c = s["cursor"]
    t.add_row("cursor", f"{c['position']} ({c['status']}), last: {c['last_candidate'] or '—'}")
    t.add_row("evaluated / rejected / passed", f"{c['evaluated']} / {c['rejected']} / {c['passed']}")
    t.add_row("search range", c["range"])
    t.add_row("candidates", ", ".join(f"{k}: {v}" for k, v in s["candidates"].items()) or "—")
    for k, v in s["providers"].items():
        t.add_row(f"provider: {k}", v)
    console.print(t)


@app.command("continue")
def continue_(
    year: YearOpt = None,
    max_candidates: Annotated[int | None, typer.Option("--max", help="Max candidates this run")] = None,
    score: Annotated[bool, typer.Option("--score", help="Also show the internal score")] = False,
) -> None:
    """Resume the systematic search exactly where it stopped (same as «اكمل»)."""
    with service() as svc:
        _, rec, text = svc.continue_search(
            year=year, max_candidates=max_candidates, progress=_progress, show_score=score
        )
    console.print(text)


@app.command()
def search(
    title: Annotated[str | None, typer.Option("--title", "-t", help="Research one specific title")] = None,
    year: YearOpt = None,
    month: Annotated[int | None, typer.Option("--month", "-m", min=1, max=12, help="Start month")] = None,
    force: Annotated[bool, typer.Option(help="Research even if blocked/excluded")] = False,
    explain: Annotated[bool, typer.Option(help="Show the full internal assessment")] = False,
) -> None:
    """Research a specific title, or position the cursor (--year/--month) and search from there."""
    with service() as svc:
        if title:
            cand = svc.research_title(title, year, force=force)
            label = cand.movie.label
            console.print(f"{label}: [bold]{cand.research_status}[/bold] — {cand.decision_reason}")
            if explain:
                console.print(svc.explain(title, year))
            return
        _, rec, text = svc.continue_search(year=year, month=month, progress=_progress)
        console.print(text)


@app.command()
def recommend(
    count: Annotated[int, typer.Option("--count", "-n", min=1, max=10)] = 1,
    score: Annotated[bool, typer.Option("--score", help="Show internal score")] = False,
    no_research: Annotated[
        bool, typer.Option("--no-research", help="Only use already researched candidates")
    ] = False,
) -> None:
    """Show HIGH-confidence recommendations (one by default). Researches more if needed."""
    with service() as svc:
        recs = svc.recommend(count, research=not no_research, show_score=score, progress=_progress)
        if not recs:
            console.print(
                svc._msg(
                    "stopped", reason="no HIGH-confidence candidate yet", position=svc.engine().position()
                )
            )
    for i, rec in enumerate(recs):
        if i:
            console.print("—" * 30)
        console.print(rec.text)


@app.command()
def feedback(
    title: str,
    rating: Annotated[
        str,
        typer.Option("--rating", "-r", help="loved|excellent|liked|good|medium|average|medium_low|disliked"),
    ],
    year: YearOpt = None,
    notes: Annotated[
        str | None, typer.Option("--notes", help="Free text (Arabic or English) - traits are extracted")
    ] = None,
    positive: Annotated[str | None, typer.Option(help="Comma-separated positive traits")] = None,
    negative: Annotated[str | None, typer.Option(help="Comma-separated negative traits")] = None,
    value: Annotated[float | None, typer.Option("--value", help="Numeric rating out of 10")] = None,
) -> None:
    """Record that you watched a movie and what you thought of it; the taste model learns from it."""
    with service() as svc:
        report = svc.feedback(title, rating, year, notes, _split(positive), _split(negative), value)
    console.print(f"[green]Saved:[/green] {report.movie}")
    for change in report.changes:
        console.print(f"  · {change}")


@app.command()
def say(text: str) -> None:
    """Natural language: «اكمل»، «شاهدته وأعجبني جدًا»، «ضعه للمشاهدة لاحقًا»، «لا يعجبني الممثلين» ..."""
    with service() as svc:
        reply = svc.handle_message(text, progress=_progress)
    console.print(reply.text)
    for change in reply.data.get("changes", []):
        console.print(f"[dim]  · {change}[/dim]")


@app.command()
def history(limit: Annotated[int, typer.Option(min=1)] = 30) -> None:
    """Recommendation history."""
    with service() as svc:
        rows = svc.repos.recommendations.list(svc.user, limit)
        t = Table("date", "movie", "confidence", "response")
        for r in rows:
            t.add_row(f"{r.recommended_at:%Y-%m-%d}", r.movie.label, r.confidence or "", r.user_response)
    console.print(t)


@app.command()
def backup() -> None:
    """Create an online backup of the SQLite database."""
    path = backup_database()
    console.print(f"[green]Backup written:[/green] {path}")


@app.command()
def serve(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8765,
) -> None:
    """Run the local API + web dashboard."""
    import uvicorn

    upgrade_database()
    uvicorn.run("mris.api.app:create_app", host=host, port=port, factory=True)


# --------------------------------------------------------------------------- watchlist
@watchlist_app.command("add")
def watchlist_add(
    title: str, year: YearOpt = None, note: Annotated[str | None, typer.Option()] = None
) -> None:
    with service() as svc:
        movie = svc.watchlist_add(title, year, note)
    console.print(f"[green]Added to watch-later:[/green] {movie.label}")


@watchlist_app.command("list")
def watchlist_list() -> None:
    with service() as svc:
        t = Table("movie", "added", "note")
        for e in svc.repos.watchlist.list(svc.user):
            t.add_row(e.movie.label, f"{e.added_at:%Y-%m-%d}", e.note or "")
    console.print(t)


@watchlist_app.command("remove")
def watchlist_remove(title: str, year: YearOpt = None) -> None:
    with service() as svc:
        ok = svc.watchlist_remove(title, year)
    console.print("[green]Removed[/green]" if ok else "[yellow]Not on the watchlist[/yellow]")


# --------------------------------------------------------------------------- rejected
@rejected_app.command("list")
def rejected_list(
    source: Annotated[str | None, typer.Option(help="Filter: user | research_pipeline")] = None,
    limit: Annotated[int, typer.Option(min=1)] = 100,
) -> None:
    """List rejected titles (you asked explicitly, so they are shown)."""
    with service() as svc:
        t = Table("movie", "date", "source", "confidence", "reason")
        for r in svc.repos.rejected.list(svc.user, source)[:limit]:
            label = f"{r.title} ({r.year})" if r.year else r.title
            t.add_row(
                label,
                f"{r.rejection_date:%Y-%m-%d}",
                r.source_of_rejection,
                r.confidence,
                r.rejection_reason[:90],
            )
    console.print(t)


@rejected_app.command("add")
def rejected_add(title: str, reason: Annotated[str, typer.Option("--reason")], year: YearOpt = None) -> None:
    with service() as svc:
        movie = svc.reject(title, year, reason)
    console.print(f"[green]Rejected:[/green] {movie.label}")


@rejected_app.command("remove")
def rejected_remove(title: str, year: YearOpt = None) -> None:
    with service() as svc:
        movie = svc.resolve_movie(title, year, create=False)
        ok = bool(movie and svc.repos.rejected.remove(svc.user, movie))
    console.print("[green]Removed from rejected[/green]" if ok else "[yellow]Not found[/yellow]")


@rejected_app.command("franchise")
def rejected_franchise(name: str, notes: Annotated[str | None, typer.Option()] = None) -> None:
    """Reject a whole franchise (e.g. "John Wick")."""
    with service() as svc:
        svc.repos.franchises.add(name, None, "strong", franchise_rejected=True, notes=notes)
    console.print(f"[green]Franchise rejected:[/green] {name}")


# --------------------------------------------------------------------------- profile
@profile_app.callback()
def profile_show(ctx: typer.Context) -> None:
    """Show the profile, weights, penalties, exclusions and learned affinities."""
    if ctx.invoked_subcommand:
        return
    with service() as svc:
        user = svc.user
        console.print(
            f"[bold]{user.name}[/bold] — language: {user.primary_language}, replies: {user.response_language}"
        )
        for rule in user.profile.get("critical_rules", []):
            console.print(f"  • {rule}")
        t = Table("type", "key", "value", "enabled", "source", "notes")
        for r in svc.repos.preferences.list(user):
            t.add_row(
                r.rule_type,
                r.key,
                f"{r.value:g}",
                "yes" if r.enabled else "no",
                r.source,
                (r.notes or "")[:50],
            )
    console.print(t)


@profile_app.command("set-rule")
def profile_set_rule(rule_type: str, key: str, value: float) -> None:
    """e.g. `mris profile set-rule penalty slow_opening 25` or `... threshold pass_score 80`."""
    valid = {r.value for r in RuleType}
    if rule_type not in valid:
        raise typer.BadParameter(f"rule_type must be one of {sorted(valid)}")
    with service() as svc:
        svc.repos.preferences.set(svc.user, rule_type, key, value, source="user")
    console.print(f"[green]{rule_type}.{key} = {value:g}[/green]")


@profile_app.command("exclusion")
def profile_exclusion(key: str, enabled: Annotated[bool, typer.Option("--enable/--disable")] = True) -> None:
    """Enable/disable an automatic-reject rule, e.g. `mris profile exclusion science_fiction --disable`."""
    with service() as svc:
        rule = svc.repos.preferences.get(svc.user, RuleType.EXCLUSION, key)
        if rule is None:
            console.print(f"[red]Unknown exclusion '{key}'[/red]")
            raise typer.Exit(1)
        rule.enabled = enabled
        rule.value = 1.0 if enabled else 0.0
        rule.source = "user"
    console.print(f"[green]{key}: {'enabled' if enabled else 'disabled'}[/green]")


@profile_app.command("language")
def profile_language(response_language: Annotated[str, typer.Argument(help="ar | en")]) -> None:
    with service() as svc:
        svc.user.response_language = response_language
    console.print(f"[green]Response language: {response_language}[/green]")


# --------------------------------------------------------------------------- database
@database_app.command("info")
def database_info() -> None:
    settings = get_settings()
    engine = get_engine()
    upgrade_database()
    with engine.connect() as conn:
        mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        tables = [
            r[0]
            for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        ]
        counts = {t: conn.exec_driver_sql(f'SELECT COUNT(*) FROM "{t}"').scalar() for t in tables}
    console.print(f"file: {settings.database_file}")
    console.print(f"revision: {current_revision(engine)} · journal_mode: {mode}")
    t = Table("table", "rows")
    for name, n in counts.items():
        t.add_row(name, str(n))
    console.print(t)


@database_app.command("migrate")
def database_migrate(revision: Annotated[str, typer.Argument()] = "head") -> None:
    upgrade_database(revision=revision)
    console.print(f"[green]Database at {revision}[/green]")


@database_app.command("vacuum")
def database_vacuum() -> None:
    with get_engine().connect() as conn:
        conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.exec_driver_sql("VACUUM")
    console.print("[green]Vacuumed[/green]")


@database_app.command("export")
def database_export(path: Annotated[Path, typer.Argument()] = Path("data/mris-export.json")) -> None:
    """Export the taste memory (feedback, references, watchlist, rejected, rules) to JSON."""
    with service() as svc:
        user = svc.user
        data = {
            "user": {"name": user.name, "profile": user.profile},
            "feedback": [
                {
                    "movie": f.movie.label,
                    "rating": f.rating_label,
                    "status": f.status,
                    "positive": f.positive_traits,
                    "negative": f.negative_traits,
                    "notes": f.reason_text,
                    "date": f.created_at.isoformat(),
                }
                for f in svc.repos.feedback.list(user)
            ],
            "references": [
                {"movie": r.movie.label, "rating": r.rating_label, "importance": r.importance}
                for r in svc.repos.references.list(user)
            ],
            "watchlist": [{"movie": e.movie.label, "note": e.note} for e in svc.repos.watchlist.list(user)],
            "rejected": [
                {
                    "movie": r.title,
                    "year": r.year,
                    "reason": r.rejection_reason,
                    "source": r.source_of_rejection,
                }
                for r in svc.repos.rejected.list(user)
            ],
            "rules": [
                {"type": r.rule_type, "key": r.key, "value": r.value, "enabled": r.enabled}
                for r in svc.repos.preferences.list(user)
            ],
        }
    path = get_settings().resolve(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]Exported to {path}[/green]")


# --------------------------------------------------------------------------- research
@research_app.command("queue")
def research_queue(
    status_filter: Annotated[str | None, typer.Option("--status")] = None,
    limit: Annotated[int, typer.Option(min=1)] = 60,
) -> None:
    with service() as svc:
        t = Table("period", "#", "candidate", "category", "status", "checked")
        for i in svc.repos.queue.list(status_filter, limit):
            t.add_row(
                f"{i.year}-{i.month:02d}",
                str(i.sort_order),
                i.candidate,
                i.release_category,
                i.research_status,
                f"{i.last_checked:%Y-%m-%d %H:%M}" if i.last_checked else "",
            )
    console.print(t)


@research_app.command("pending")
def research_pending() -> None:
    """Candidates waiting for more evidence (with the searches to run for them)."""
    from mris.research.pipeline import QUERY_PLAN

    with service() as svc:
        cands = svc.repos.candidates.by_status("insufficient_evidence") + svc.repos.candidates.by_status(
            "queued"
        )
        for cand in cands[:25]:
            m = cand.movie
            console.print(f"[bold]{m.label}[/bold] — {cand.decision_reason or cand.research_status}")
            for _, purpose, template in QUERY_PLAN:
                console.print(
                    f"   {purpose:15s} {template.format(t=chr(34) + m.title + chr(34), y=m.year or '')}"
                )


@research_app.command("add-evidence")
def research_add_evidence(
    title: str,
    url: Annotated[str, typer.Option("--url", help="Where the text comes from")],
    text: Annotated[str, typer.Option("--text", help="The review / comment text (verbatim)")],
    year: YearOpt = None,
    source_type: Annotated[
        str | None, typer.Option("--type", help="professional|audience|trailer|manual")
    ] = None,
    publisher: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Add a real source for a title and re-score it (works without any API key)."""
    with service() as svc:
        cand = svc.add_evidence(title, year, url, text, source_type, publisher)
        console.print(f"{cand.movie.label}: {cand.research_status} — {cand.decision_reason}")


@research_app.command("add-candidate")
def research_add_candidate(
    title: str,
    year: Annotated[int, typer.Option("--year", "-y")],
    month: Annotated[int, typer.Option("--month", "-m", min=1, max=12)],
    category: Annotated[str, typer.Option(help="theatrical|streaming|wide|independent")] = "unknown",
) -> None:
    """Queue a candidate manually for a given month (used when no discovery provider is configured)."""
    with service() as svc:
        movie = svc.queue_candidate(title, year, month, category)
    console.print(f"[green]Queued:[/green] {movie.label} for {year}-{month:02d}")


@research_app.command("explain")
def research_explain(title: str, year: YearOpt = None) -> None:
    """Show the full internal assessment of a researched title (scores, evidence, risks)."""
    with service() as svc:
        text = svc.explain(title, year)
    console.print(text or "[yellow]Not researched yet[/yellow]")


@research_app.command("evaluate")
def research_evaluate(title: str, year: YearOpt = None) -> None:
    """Re-score one title from stored evidence (no network)."""
    with service() as svc:
        movie = svc.resolve_movie(title, year, create=False)
        cand = svc.repos.candidates.for_movie(movie) if movie else None
        if not cand:
            console.print("[yellow]Not researched yet[/yellow]")
            raise typer.Exit(1)
        result = svc.pipeline.evaluate(cand)
        console.print(f"{movie.label}: {result.status.value} — {result.reason}")


@research_app.command("rescore")
def research_rescore() -> None:
    """Re-score every stored candidate with the current (learned) taste model."""
    with service() as svc:
        n = svc.rescore_all()
    console.print(f"[green]Re-scored {n} candidates[/green]")


@research_app.command("enrich-references")
def research_enrich_references() -> None:
    """Derive trait vectors for reference movies from verified metadata (needs TMDb)."""
    with service() as svc:
        n = svc.enrich_references()
    console.print(f"[green]Enriched {n} reference movies[/green]")


@research_app.command("retry")
def research_retry() -> None:
    """Put candidates that failed with provider errors back in the queue."""
    with service() as svc:
        items = svc.repos.queue.list("error", 10_000)
        for item in items:
            item.research_status = "queued"
    console.print(f"[green]{len(items)} items re-queued[/green]")


@research_app.command("events")
def research_events(limit: Annotated[int, typer.Option(min=1)] = 40) -> None:
    with service() as svc:
        t = Table("time", "type", "step", "message")
        for e in reversed(svc.repos.events.recent(limit)):
            t.add_row(f"{e.created_at:%m-%d %H:%M:%S}", e.event_type, str(e.step or ""), e.message[:100])
    console.print(t)


@research_app.command("cursor")
def research_cursor(
    year: Annotated[int, typer.Option("--year", "-y")],
    month: Annotated[int, typer.Option("--month", "-m", min=1, max=12)] = 1,
) -> None:
    """Move the research cursor explicitly."""
    with service() as svc:
        svc.engine().jump_to(year, month)
        console.print(f"[green]Cursor at {svc.engine().position()}[/green]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
