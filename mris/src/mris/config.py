"""Application configuration.

All settings come from environment variables prefixed with ``MRIS_`` (or a ``.env`` file in
the project root).  Nothing here is required: missing provider keys simply disable the
corresponding research step, and the research engine then reports the evidence as missing
instead of guessing.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent
# src/mris -> src -> project root (valid for source checkouts and editable installs)
PROJECT_ROOT = PACKAGE_DIR.parent.parent


def _default_migrations_dir() -> Path:
    bundled = PACKAGE_DIR / "_migrations"
    if bundled.is_dir():
        return bundled
    return PROJECT_ROOT / "migrations"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MRIS_",
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: Path = Field(default=Path("data/mris.db"))
    backup_dir: Path = Field(default=Path("data/backups"))
    backup_keep: int = 20

    tmdb_api_key: str = ""
    omdb_api_key: str = ""
    search_provider: Literal["brave", "tavily", "none"] = "none"
    brave_api_key: str = ""
    tavily_api_key: str = ""
    fetch_pages: bool = True

    search_start_year: int = 2026
    search_end_year: int = 2010
    min_vote_count: int = 15
    max_discovery_pages: int = 5
    max_candidates_per_run: int = 150

    pass_threshold: float = 75.0
    reject_threshold: float = 55.0

    http_timeout: float = 20.0
    web_request_delay: float = 1.1  # seconds between web-search calls (free API tiers rate-limit)
    max_results_per_query: int = 6

    def resolve(self, path: Path) -> Path:
        return path if path.is_absolute() else (PROJECT_ROOT / path)

    @property
    def database_file(self) -> Path:
        return self.resolve(self.db_path)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_file}"

    @property
    def backup_path(self) -> Path:
        return self.resolve(self.backup_dir)

    @property
    def migrations_dir(self) -> Path:
        return _default_migrations_dir()

    @property
    def web_search_enabled(self) -> bool:
        if self.search_provider == "brave":
            return bool(self.brave_api_key)
        if self.search_provider == "tavily":
            return bool(self.tavily_api_key)
        return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
