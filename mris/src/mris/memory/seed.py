"""Initial taste memory for the configured user (sections 2-7 and 29 of the specification).

Seeding is idempotent: running it twice never duplicates rows and never overwrites values the
user or the learning loop changed afterwards.  Years are stored only where the user gave them.
"""

from __future__ import annotations

from typing import Any

from mris.memory.learning import ensure_default_rules
from mris.memory.vocabulary import characteristics_to_traits
from mris.models import User
from mris.repositories import Repos

PROFILE: dict[str, Any] = {
    "name": "Haitham",
    "primary_language": "ar",
    "response_language": "ar",
    "high_priority": [
        "strong story",
        "strong acting",
        "strong opening",
        "events begin early",
        "clear story progression",
        "logical sequence of events",
        "continuous tension",
        "action that serves the story",
        "crime",
        "revenge",
        "rescue",
        "survival",
        "escape",
        "pursuit / chases",
        "heists",
        "police action",
        "disasters",
        "industrial / offshore disasters",
        "time pressure",
        "high-stakes situations",
        "modern settings",
        "strong production quality",
        "recognizable / convincing actors",
        "English-language productions",
    ],
    "critical_rules": [
        "The first 10-15 minutes are critical: credible evidence of a slow beginning, long exposition, "
        "excessive setup, prolonged dialogue before the main conflict, a weak or confusing opening "
        "normally means rejection.",
        "Dialogue is not automatically bad: reject it only when it stops the story/action.",
        "Confined locations, violence, gunfire and exaggeration are acceptable when events stay active and "
        "the gunfire serves rescue, hostage, robbery, protection, revenge, crime or pursuit.",
        "Reject military-style gunfire without a clear civilian story purpose.",
        "A movie must be understandable on its own (no franchise knowledge required).",
        "Cast appeal matters: a likely cast problem is a serious risk.",
        "Avoid excessive shaky cam / chaotic editing / visually confusing action.",
        "Realism is not required, but plotting must be coherent (no stupid decisions or forced coincidences).",
    ],
    "output": {"default_count": 1, "show_scores": False, "only_high_confidence": True},
    "lessons": {
        "Mutiny": "Loved: story + acting + event progression matter greatly; action alone is insufficient.",
        "The Amateur": "Disliked within 10 minutes: slow openings are heavily penalised.",
        "Carry-On": "Medium: a generic high-concept thriller is not enough.",
        "Collateral": "Likes an ordinary person caught in a dangerous criminal situation, "
        "but wants modern / high-energy execution.",
        "Ballerina": "Rejected: relies on John Wick knowledge - standalone clarity is essential.",
        "Reckless": "Rejected after the trailer because the actors did not appeal - cast appeal matters.",
        "Clutch": "Rejected: felt 'dead' / too small - production quality and cinematic presence matter.",
    },
}

REFERENCES: list[dict[str, Any]] = [
    {
        "title": "Last Breath",
        "year": 2025,
        "rating": "excellent",
        "label": "excellent / top-tier",
        "importance": "very_high",
        "characteristics": [
            "realistic survival",
            "offshore",
            "rescue",
            "time pressure",
            "continuous danger",
            "strong tension",
            "serious tone",
        ],
    },
    {
        "title": "Runner",
        "year": 2026,
        "rating": "loved",
        "label": "loved / extremely positive",
        "importance": "very_high",
        "characteristics": [
            "fast pacing",
            "immediate danger",
            "rescue",
            "pursuit",
            "continuous movement",
            "modern",
            "entertaining",
        ],
    },
    {
        "title": "Mutiny",
        "year": 2026,
        "rating": "loved",
        "label": "loved / extremely positive",
        "importance": "very_high",
        "characteristics": [
            "strong acting",
            "strong story",
            "excellent event progression",
            "clear plot",
            "action",
            "pursuit",
            "crime",
            "strong production",
            "good opening",
            "entertaining",
        ],
    },
    {
        "title": "Fuze",
        "year": 2026,
        "rating": "loved",
        "label": "loved",
        "importance": "high",
        "characteristics": ["modern crime", "heist", "fast pacing", "movement", "chaos", "strong execution"],
    },
    {
        "title": "The Town",
        "year": 2010,
        "rating": "excellent",
        "label": "excellent",
        "importance": "high",
        "characteristics": ["crime", "heist", "strong acting", "strong story", "realistic action"],
    },
    {
        "title": "Taken",
        "year": 2008,
        "rating": "loved",
        "label": "loved",
        "importance": "high",
        "characteristics": ["rescue", "pursuit", "revenge", "immediate conflict", "clear objective"],
    },
    {
        "title": "Man on Fire",
        "year": 2004,
        "rating": "excellent",
        "label": "excellent",
        "importance": "high",
        "characteristics": [],
    },
    {
        "title": "Nobody",
        "year": 2021,
        "rating": "excellent",
        "label": "excellent",
        "importance": "high",
        "characteristics": [],
    },
    {
        "title": "The Equalizer",
        "year": 2014,
        "rating": "excellent",
        "label": "excellent",
        "importance": "high",
        "characteristics": [],
    },
    {
        "title": "Wrath of Man",
        "year": 2021,
        "rating": "excellent",
        "label": "excellent",
        "importance": "high",
        "characteristics": [],
    },
    {
        "title": "The Accountant",
        "year": 2016,
        "rating": "liked",
        "label": "liked",
        "importance": "medium",
        "characteristics": [],
    },
    {
        "title": "Law Abiding Citizen",
        "year": 2009,
        "rating": "liked",
        "label": "liked",
        "importance": "medium",
        "characteristics": [],
    },
    {
        "title": "Deepwater Horizon",
        "year": 2016,
        "rating": "liked",
        "label": "liked",
        "importance": "high",
        "characteristics": ["industrial disaster", "offshore", "evacuation", "survival", "realistic danger"],
    },
]

FEEDBACK: list[dict[str, Any]] = [
    {"title": "The Rip", "year": 2026, "rating": "medium", "importance": "high"},
    {
        "title": "Carry-On",
        "year": 2024,
        "rating": "medium",
        "importance": "high",
        "negative": ["generic_high_concept"],
        "notes": "Generic high-concept thriller is not enough.",
    },
    {
        "title": "The Amateur",
        "year": 2025,
        "rating": "disliked",
        "importance": "very_high",
        "negative": ["slow_opening", "slow_pacing", "low_initial_engagement"],
        "notes": "Extremely slow; became boring within the first 10 minutes.",
    },
    {"title": "The Accountant 2", "year": 2025, "rating": "disliked", "importance": "medium"},
    {"title": "Den of Thieves", "year": 2018, "rating": "disliked", "importance": "medium"},
    {
        "title": "Ambulance",
        "year": 2022,
        "rating": "average",
        "importance": "high",
        "negative": ["chaotic_camera"],
        "notes": "Disliked the filming / cinematography.",
    },
    {
        "title": "Crime 101",
        "year": 2026,
        "rating": "medium_low",
        "importance": "high",
        "negative": ["weak_tension"],
        "notes": "Acceptable / medium-low: did not take the user's breath away.",
    },
    {"title": "Twisters", "year": 2024, "rating": "average", "importance": "medium"},
    {"title": "The Lost Bus", "year": 2025, "rating": "good", "rating_value": 7.0, "importance": "medium"},
    {"title": "Dead of Winter", "year": 2025, "rating": "good", "importance": "medium"},
    {"title": "A Working Man", "year": 2025, "rating": "good", "importance": "medium"},
    {"title": "Plane", "year": 2023, "rating": "good", "importance": "medium"},
    {"title": "The Impossible", "year": 2012, "rating": "disliked", "importance": "medium"},
    {
        "title": "The Night Manager",
        "year": None,
        "media_type": "tv",
        "rating": "liked",
        "importance": "high",
        "negative": ["excessive_dialogue"],
        "notes": "Liked, but too much dialogue.",
    },
    {
        "title": "The Terminal List",
        "year": None,
        "media_type": "tv",
        "rating": "disliked",
        "importance": "high",
        "negative": ["slow_pacing"],
        "notes": "Season 1 - boring.",
        "aliases": ["Terminal List", "Terminal List Season 1"],
    },
]

WATCHLIST: list[dict[str, Any]] = [
    {"title": "Beast", "year": 2026, "note": None},
    {"title": "Hotel Mumbai", "year": 2018, "note": None},
    {
        "title": "Fight or Flight",
        "year": 2025,
        "note": "User watched the first 5 minutes; comedy tone may be stronger than desired; "
        "user explicitly asked to keep it for later.",
    },
]

REJECTED: list[dict[str, Any]] = [
    {
        "title": "Ballerina",
        "year": 2025,
        "reason": "Depends on the John Wick universe (not standalone).",
        "source": "user",
        "franchise": "John Wick",
    },
    {
        "title": "Reckless",
        "year": None,
        "reason": "Rejected after the trailer: the actors did not appeal.",
        "source": "user_trailer",
        "traits": ["cast_mismatch"],
    },
    {
        "title": "Clutch",
        "year": None,
        "reason": "Felt 'dead' / too small - weak cinematic presence.",
        "source": "user",
        "traits": ["low_energy", "low_production"],
    },
]

NOTES: list[dict[str, Any]] = [
    {
        "title": "Collateral",
        "year": 2004,
        "traits": ["ordinary_person_in_danger", "crime"],
        "note": "User likes an ordinary person caught in a dangerous criminal situation, but wants modern / "
        "high-energy execution.",
    },
]


def seed_initial_data(repos: Repos, profile: dict[str, Any] | None = None) -> tuple[User, bool]:
    """Create the user and the initial memory. Returns (user, created_now)."""
    profile = profile or PROFILE
    user, created = repos.users.get_or_create(
        profile["name"],
        primary_language=profile.get("primary_language", "ar"),
        response_language=profile.get("response_language", "ar"),
        profile={
            k: v for k, v in profile.items() if k not in ("name", "primary_language", "response_language")
        },
    )
    ensure_default_rules(repos, user)
    if user.profile.get("seeded"):
        return user, False

    for ref in REFERENCES:
        movie, _ = repos.movies.get_or_create(ref["title"], ref["year"])
        repos.references.upsert(user, movie, ref["rating"], ref["importance"], notes=ref["label"])
        traits = characteristics_to_traits(ref["characteristics"])
        if traits:
            repos.movies.set_traits(movie, traits, source="seed")
        if not repos.feedback.latest(user, movie):
            repos.feedback.add(
                user,
                movie,
                ref["rating"],
                status="watched",
                importance_for_learning=ref["importance"],
                positive_traits=sorted(traits),
                source="seed",
                reason_text=ref["label"],
            )

    for fb in FEEDBACK:
        movie, _ = repos.movies.get_or_create(
            fb["title"], fb["year"], media_type=fb.get("media_type", "movie")
        )
        for alias in fb.get("aliases", []):
            repos.movies.add_alias(movie, alias)
        if not repos.feedback.latest(user, movie):
            repos.feedback.add(
                user,
                movie,
                fb["rating"],
                status="watched",
                rating_value=fb.get("rating_value"),
                reason_text=fb.get("notes"),
                negative_traits=fb.get("negative", []),
                importance_for_learning=fb["importance"],
                source="seed",
            )
        if fb.get("negative"):
            repos.movies.set_traits(movie, fb["negative"], source="seed")

    for item in WATCHLIST:
        movie, _ = repos.movies.get_or_create(item["title"], item["year"])
        repos.watchlist.add(user, movie, note=item["note"])

    for rej in REJECTED:
        movie, _ = repos.movies.get_or_create(rej["title"], rej["year"])
        repos.rejected.add(user, movie, rej["reason"], rej["source"], "HIGH")
        if rej.get("traits"):
            repos.movies.set_traits(movie, rej["traits"], source="seed")
        if rej.get("franchise"):
            repos.franchises.add(
                rej["franchise"],
                movie,
                "strong",
                franchise_rejected=False,
                notes="Spin-off that relies on John Wick knowledge.",
            )

    for note in NOTES:
        movie, _ = repos.movies.get_or_create(note["title"], note["year"])
        repos.movies.set_traits(movie, note["traits"], source="seed")

    user.profile = {**user.profile, "seeded": True}
    repos.session.flush()
    return user, True
