"""Load the initial taste profile (references, feedback, watchlist, rejections, rules).

Idempotent: re-running never duplicates rows nor overwrites learned values.
"""

from mris.database import session_scope, upgrade_database
from mris.memory import seed_initial_data
from mris.repositories import Repos

if __name__ == "__main__":
    upgrade_database()
    with session_scope() as session:
        user, created = seed_initial_data(Repos(session))
        print(("Seeded profile for " if created else "Profile already seeded: ") + user.name)
