from __future__ import annotations

from datetime import date

import pytest

from mris.config import Settings
from mris.database.engine import build_engine, make_session_factory
from mris.database.migrate import upgrade_database
from mris.service import MRIS
from tests.fixtures.fake_providers import fake_providers

TODAY = date(2026, 10, 1)


@pytest.fixture()
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    upgrade_database(url)
    return url


@pytest.fixture()
def engine(db_url):
    eng = build_engine(db_url)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    s = make_session_factory(engine)()
    yield s
    s.close()


@pytest.fixture()
def settings(tmp_path):
    return Settings(
        _env_file=None,
        db_path=tmp_path / "test.db",
        backup_dir=tmp_path / "backups",
        search_start_year=2026,
        search_end_year=2025,
        web_request_delay=0,
        max_candidates_per_run=50,
    )


@pytest.fixture()
def providers():
    return fake_providers()


@pytest.fixture()
def svc(session, providers, settings):
    service = MRIS(session, providers=providers, settings=settings, today=TODAY)
    service.init()
    return service
