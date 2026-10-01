"""'Never recommend again' rules (section 24). Checked before research and again at display time."""

from __future__ import annotations

from mris.models import Movie, RatingLabel, User
from mris.repositories import Repos
from mris.text import normalize_text


def block_reason(repos: Repos, user: User, movie: Movie, enabled: set[str] | None = None) -> str | None:
    """Return the exclusion key that blocks this movie, or None."""

    def on(key: str) -> bool:
        return enabled is None or key in enabled

    if on("previously_rejected") and repos.rejected.get(user, movie):
        return "previously_rejected"
    feedback = repos.feedback.latest(user, movie)
    if feedback is not None:
        try:
            label = RatingLabel(feedback.rating_label)
        except ValueError:
            label = None
        if label is not None and label.is_medium and on("medium_rating"):
            return "medium_rating"
        if feedback.status in ("watched", "partially_watched") and on("previously_watched"):
            return "previously_watched"
    entry = repos.watchlist.get(user, movie)
    if entry is not None and entry.status == "watch_later" and on("on_watchlist"):
        return "on_watchlist"
    if on("declined_recommendation") and any(
        r.user_response == "declined" for r in repos.recommendations.for_movie(user, movie)
    ):
        return "declined_recommendation"
    if on("rejected_franchise"):
        rejected = repos.franchises.rejected_franchises()
        dep = repos.franchises.for_movie(movie)
        if dep and normalize_text(dep.franchise_name) in rejected:
            return "rejected_franchise"
        if movie.collection_name:
            name = normalize_text(movie.collection_name.replace("Collection", ""))
            if name in rejected or normalize_text(movie.collection_name) in rejected:
                return "rejected_franchise"
    return None


def already_recommended(repos: Repos, user: User, movie: Movie) -> bool:
    return bool(repos.recommendations.for_movie(user, movie))
