from typer.testing import CliRunner

from mris.cli.app import app
from mris.config import reset_settings_cache
from mris.database.engine import get_engine


def test_cli_init_status_feedback(tmp_path, monkeypatch):
    monkeypatch.setenv("MRIS_DB_PATH", str(tmp_path / "cli.db"))
    monkeypatch.setenv("MRIS_BACKUP_DIR", str(tmp_path / "bk"))
    monkeypatch.setenv("MRIS_TMDB_API_KEY", "")
    monkeypatch.setenv("MRIS_SEARCH_PROVIDER", "none")
    reset_settings_cache()
    get_engine.cache_clear()
    runner = CliRunner()
    try:
        r = runner.invoke(app, ["init"])
        assert r.exit_code == 0, r.output
        r = runner.invoke(app, ["status"])
        assert r.exit_code == 0 and "Haitham" in r.output
        r = runner.invoke(
            app,
            [
                "feedback",
                "Mutiny",
                "--rating",
                "loved",
                "--notes",
                "Excellent acting, story and event progression",
            ],
        )
        assert r.exit_code == 0 and "Mutiny" in r.output
        r = runner.invoke(app, ["watchlist", "add", "Beast", "--year", "2026"])
        assert r.exit_code == 0
        r = runner.invoke(app, ["continue"])
        assert r.exit_code == 0  # no provider: explains instead of inventing results
        r = runner.invoke(app, ["backup"])
        assert r.exit_code == 0 and (tmp_path / "bk").exists()
        r = runner.invoke(app, ["database", "info"])
        assert r.exit_code == 0 and "wal" in r.output
    finally:
        get_engine.cache_clear()
        reset_settings_cache()
