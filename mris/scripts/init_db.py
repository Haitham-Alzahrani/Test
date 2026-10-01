"""Create / upgrade the MRIS database to the latest migration (no seed data)."""

from mris.config import get_settings
from mris.database import upgrade_database

if __name__ == "__main__":
    upgrade_database()
    print(f"Database ready at {get_settings().database_file}")
