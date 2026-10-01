"""Online SQLite backups using the sqlite3 backup API (safe while the DB is in use)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from mris.config import get_settings


def backup_database(
    db_file: Path | None = None, backup_dir: Path | None = None, keep: int | None = None
) -> Path:
    settings = get_settings()
    db_file = db_file or settings.database_file
    backup_dir = backup_dir or settings.backup_path
    keep = settings.backup_keep if keep is None else keep
    if not db_file.exists():
        raise FileNotFoundError(f"Database not found: {db_file}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{db_file.stem}-{datetime.now():%Y%m%d-%H%M%S-%f}.db"
    src = sqlite3.connect(db_file)
    dst = sqlite3.connect(target)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()
    if keep > 0:
        backups = sorted(backup_dir.glob(f"{db_file.stem}-*.db"))
        for old in backups[:-keep]:
            old.unlink(missing_ok=True)
    return target
