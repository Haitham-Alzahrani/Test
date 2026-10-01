from mris.database.backup import backup_database
from mris.models import RuleType
from mris.recommendation.blocklist import block_reason


def test_seed_is_idempotent_and_complete(svc):
    user, created = svc.init()
    assert created is False
    s = svc.status()
    assert s["references"] == 13
    assert s["watchlist"] == 3
    assert s["rejected"] == 3
    assert s["disliked"] == 5


def test_blocklist_covers_watched_rejected_watchlist_medium(svc):
    user = svc.user
    find = svc.repos.movies.find
    assert block_reason(svc.repos, user, find("The Amateur", 2025)) == "previously_watched"
    assert block_reason(svc.repos, user, find("Carry-On", 2024)) == "medium_rating"
    assert block_reason(svc.repos, user, find("Ballerina", 2025)) == "previously_rejected"
    assert block_reason(svc.repos, user, find("Beast", 2026)) == "on_watchlist"
    # Reckless was rejected without a year; a dated candidate with that title still matches
    assert block_reason(svc.repos, user, find("Reckless", 2025)) == "previously_rejected"


def test_feedback_learning_adjusts_rules(svc):
    user = svc.user
    before = svc.repos.preferences.get(user, RuleType.PENALTY, "slow_opening").value
    reply = svc.handle_message("Night Run بطيء جدا ومللت منه من اول عشر دقايق")
    assert reply.data["rating"] == "disliked"
    after = svc.repos.preferences.get(user, RuleType.PENALTY, "slow_opening").value
    assert after > before
    movie = svc.repos.movies.find("Night Run")
    assert block_reason(svc.repos, user, movie) == "previously_watched"


def test_loved_feedback_creates_reference(svc):
    svc.feedback("Iron Tide", "loved", 2026, notes="التمثيل والقصه ممتازه")
    refs = {r.movie.title for r in svc.repos.references.list(svc.user)}
    assert "Iron Tide" in refs


def test_backup(svc, settings, tmp_path):
    svc.session.commit()
    path = backup_database(settings.database_file, tmp_path / "bk", keep=2)
    assert path.exists() and path.stat().st_size > 0


def test_feedback_never_downgrades_reference_importance(svc):
    svc.feedback("Mutiny", "loved", 2026, notes="great")
    ref = next(r for r in svc.repos.references.list(svc.user) if r.movie.title == "Mutiny")
    assert ref.importance == "very_high"
    assert ref.notes == "loved / extremely positive"


def test_good_rating_does_not_become_reference(svc):
    svc.feedback("Some Film", "good", 2025)
    assert "Some Film" not in {r.movie.title for r in svc.repos.references.list(svc.user)}
