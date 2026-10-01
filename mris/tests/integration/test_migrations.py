from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext

from mris.database.migrate import current_revision
from mris.models import Base

EXPECTED = {
    "users",
    "movies",
    "movie_aliases",
    "movie_feedback",
    "reference_movies",
    "movie_traits",
    "watchlist",
    "rejected_movies",
    "candidate_movies",
    "research_events",
    "research_sources",
    "research_cursor",
    "preference_rules",
    "actor_preferences",
    "franchise_dependencies",
    "recommendation_history",
    "research_queue",
}


def test_migrations_create_schema_matching_models(engine):
    with engine.connect() as conn:
        tables = {r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        assert EXPECTED <= tables
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations differ: {diff}"
    assert current_revision(engine) == "0001"
