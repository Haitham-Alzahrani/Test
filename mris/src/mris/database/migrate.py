"""Programmatic Alembic access so `mris init` works without an alembic.ini on PATH."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine

from mris.config import get_settings


def alembic_config(database_url: str | None = None) -> Config:
    settings = get_settings()
    cfg = Config()
    cfg.set_main_option("script_location", str(settings.migrations_dir))
    cfg.set_main_option("sqlalchemy.url", database_url or settings.database_url)
    return cfg


def upgrade_database(database_url: str | None = None, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()
