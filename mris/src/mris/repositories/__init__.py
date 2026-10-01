from mris.repositories.movies import MovieRepository
from mris.repositories.research import (
    CandidateRepository,
    CursorRepository,
    EventRepository,
    QueueRepository,
    RecommendationRepository,
)
from mris.repositories.taste import (
    ActorPreferenceRepository,
    FeedbackRepository,
    FranchiseRepository,
    PreferenceRepository,
    ReferenceRepository,
    RejectedRepository,
    UserRepository,
    WatchlistRepository,
)


class Repos:
    """Convenience bundle of every repository bound to one session."""

    def __init__(self, session) -> None:
        self.session = session
        self.movies = MovieRepository(session)
        self.users = UserRepository(session)
        self.feedback = FeedbackRepository(session)
        self.references = ReferenceRepository(session)
        self.watchlist = WatchlistRepository(session)
        self.rejected = RejectedRepository(session)
        self.preferences = PreferenceRepository(session)
        self.actors = ActorPreferenceRepository(session)
        self.franchises = FranchiseRepository(session)
        self.cursor = CursorRepository(session)
        self.queue = QueueRepository(session)
        self.candidates = CandidateRepository(session)
        self.events = EventRepository(session)
        self.recommendations = RecommendationRepository(session)


__all__ = [
    "ActorPreferenceRepository",
    "CandidateRepository",
    "CursorRepository",
    "EventRepository",
    "FeedbackRepository",
    "FranchiseRepository",
    "MovieRepository",
    "PreferenceRepository",
    "QueueRepository",
    "RecommendationRepository",
    "ReferenceRepository",
    "RejectedRepository",
    "Repos",
    "UserRepository",
    "WatchlistRepository",
]
