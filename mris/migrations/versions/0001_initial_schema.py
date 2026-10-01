"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-01 19:36:05.362924
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "movies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("normalized_title", sa.String(length=300), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("media_type", sa.String(length=10), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("imdb_id", sa.String(length=20), nullable=True),
        sa.Column("original_language", sa.String(length=10), nullable=True),
        sa.Column("countries", sa.JSON(), nullable=False),
        sa.Column("genres", sa.JSON(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("runtime", sa.Integer(), nullable=True),
        sa.Column("director", sa.String(length=200), nullable=True),
        sa.Column("cast", sa.JSON(), nullable=False),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("collection_name", sa.String(length=300), nullable=True),
        sa.Column("collection_position", sa.Integer(), nullable=True),
        sa.Column("budget", sa.Integer(), nullable=True),
        sa.Column("production_companies", sa.JSON(), nullable=False),
        sa.Column("trailer_url", sa.String(length=500), nullable=True),
        sa.Column("ratings", sa.JSON(), nullable=False),
        sa.Column("metadata_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("imdb_id"),
        sa.UniqueConstraint("tmdb_id"),
    )
    with op.batch_alter_table("movies", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_movies_normalized_title"), ["normalized_title"], unique=False)
        batch_op.create_index("ix_movies_normalized_title_year", ["normalized_title", "year"], unique=False)
        batch_op.create_index("ix_movies_release_date", ["release_date"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("primary_language", sa.String(length=10), nullable=False),
        sa.Column("response_language", sa.String(length=10), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "actor_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=True),
        sa.Column("sentiment", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("actor_preferences", schema=None) as batch_op:
        batch_op.create_index("ix_actor_pref_name", ["normalized_name"], unique=False)

    op.create_table(
        "candidate_movies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("discovery_source", sa.String(length=60), nullable=False),
        sa.Column("release_category", sa.String(length=20), nullable=False),
        sa.Column("research_status", sa.String(length=30), nullable=False),
        sa.Column("research_version", sa.Integer(), nullable=False),
        sa.Column("opening_score", sa.Float(), nullable=True),
        sa.Column("opening_confidence", sa.String(length=10), nullable=True),
        sa.Column("opening_evidence", sa.JSON(), nullable=False),
        sa.Column("opening_event_start_minutes", sa.Float(), nullable=True),
        sa.Column("pacing", sa.Float(), nullable=True),
        sa.Column("slow_burn", sa.Boolean(), nullable=False),
        sa.Column("story_clarity", sa.Float(), nullable=True),
        sa.Column("story_progression", sa.Float(), nullable=True),
        sa.Column("event_continuity", sa.Float(), nullable=True),
        sa.Column("plot_coherence", sa.Float(), nullable=True),
        sa.Column("dialogue_to_event_ratio", sa.Float(), nullable=True),
        sa.Column("tension_continuity", sa.Float(), nullable=True),
        sa.Column("action_quality", sa.Float(), nullable=True),
        sa.Column("cast_strength", sa.Float(), nullable=True),
        sa.Column("acting_quality", sa.Float(), nullable=True),
        sa.Column("character_credibility", sa.Float(), nullable=True),
        sa.Column("production_quality", sa.Float(), nullable=True),
        sa.Column("cinematography_quality", sa.Float(), nullable=True),
        sa.Column("action_clarity", sa.Float(), nullable=True),
        sa.Column("camera_stability", sa.Float(), nullable=True),
        sa.Column("visual_quality", sa.Float(), nullable=True),
        sa.Column("realism", sa.Float(), nullable=True),
        sa.Column("internal_logic", sa.Float(), nullable=True),
        sa.Column("exaggeration_level", sa.Float(), nullable=True),
        sa.Column("franchise_dependency", sa.String(length=20), nullable=True),
        sa.Column("reference_similarity", sa.Float(), nullable=True),
        sa.Column("similar_references", sa.JSON(), nullable=False),
        sa.Column("risks", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("hard_exclusion_reason", sa.Text(), nullable=True),
        sa.Column("score_breakdown", sa.JSON(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.String(length=10), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movie_id"),
    )
    with op.batch_alter_table("candidate_movies", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_candidate_movies_research_status"), ["research_status"], unique=False
        )

    op.create_table(
        "franchise_dependencies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("franchise_name", sa.String(length=200), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=True),
        sa.Column("dependency_level", sa.String(length=20), nullable=False),
        sa.Column("franchise_rejected", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("franchise_dependencies", schema=None) as batch_op:
        batch_op.create_index("ix_franchise_name", ["franchise_name"], unique=False)

    op.create_table(
        "movie_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=300), nullable=False),
        sa.Column("normalized_alias", sa.String(length=300), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movie_id", "normalized_alias", name="uq_alias_movie"),
    )
    with op.batch_alter_table("movie_aliases", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_movie_aliases_movie_id"), ["movie_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_movie_aliases_normalized_alias"), ["normalized_alias"], unique=False
        )

    op.create_table(
        "movie_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("rating_label", sa.String(length=30), nullable=False),
        sa.Column("rating_value", sa.Float(), nullable=True),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("positive_traits", sa.JSON(), nullable=False),
        sa.Column("negative_traits", sa.JSON(), nullable=False),
        sa.Column("importance_for_learning", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("movie_feedback", schema=None) as batch_op:
        batch_op.create_index("ix_feedback_user_movie", ["user_id", "movie_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_movie_feedback_movie_id"), ["movie_id"], unique=False)

    op.create_table(
        "movie_traits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("trait", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movie_id", "trait", "source", name="uq_trait_movie_source"),
    )
    with op.batch_alter_table("movie_traits", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_movie_traits_movie_id"), ["movie_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_movie_traits_trait"), ["trait"], unique=False)

    op.create_table(
        "preference_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rule_type", sa.String(length=20), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "rule_type", "key", name="uq_rule_user_type_key"),
    )
    with op.batch_alter_table("preference_rules", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_preference_rules_rule_type"), ["rule_type"], unique=False)

    op.create_table(
        "reference_movies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("rating_label", sa.String(length=30), nullable=False),
        sa.Column("importance", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "movie_id", name="uq_reference_user_movie"),
    )
    with op.batch_alter_table("reference_movies", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_reference_movies_movie_id"), ["movie_id"], unique=False)

    op.create_table(
        "rejected_movies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=False),
        sa.Column("rejection_date", sa.DateTime(), nullable=False),
        sa.Column("source_of_rejection", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("rejected_movies", schema=None) as batch_op:
        batch_op.create_index("ix_rejected_user_movie", ["user_id", "movie_id"], unique=False)

    op.create_table(
        "research_cursor",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("month_discovered", sa.Boolean(), nullable=False),
        sa.Column("last_queue_item_id", sa.Integer(), nullable=True),
        sa.Column("last_candidate", sa.String(length=300), nullable=True),
        sa.Column("range_start_year", sa.Integer(), nullable=False),
        sa.Column("range_end_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("candidates_evaluated", sa.Integer(), nullable=False),
        sa.Column("candidates_rejected", sa.Integer(), nullable=False),
        sa.Column("candidates_passed", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "movie_id", name="uq_watchlist_user_movie"),
    )
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_watchlist_movie_id"), ["movie_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_watchlist_status"), ["status"], unique=False)

    op.create_table(
        "recommendation_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("recommended_at", sa.DateTime(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.String(length=10), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("research_version", sa.Integer(), nullable=False),
        sa.Column("user_response", sa.String(length=20), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_movies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("recommendation_history", schema=None) as batch_op:
        batch_op.create_index("ix_rec_user_movie", ["user_id", "movie_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_recommendation_history_recommended_at"), ["recommended_at"], unique=False
        )

    op.create_table(
        "research_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("step", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("research_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_research_events_candidate_id"), ["candidate_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_research_events_created_at"), ["created_at"], unique=False)

    op.create_table(
        "research_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("candidate", sa.String(length=300), nullable=False),
        sa.Column("discovery_source", sa.String(length=60), nullable=False),
        sa.Column("release_category", sa.String(length=20), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("research_status", sa.String(length=30), nullable=False),
        sa.Column("last_checked", sa.DateTime(), nullable=True),
        sa.Column("next_action", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_movies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "month", "movie_id", name="uq_queue_period_movie"),
    )
    with op.batch_alter_table("research_queue", schema=None) as batch_op:
        batch_op.create_index("ix_queue_period_order", ["year", "month", "sort_order"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_research_queue_research_status"), ["research_status"], unique=False
        )

    op.create_table(
        "research_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("domain", sa.String(length=200), nullable=True),
        sa.Column("publisher", sa.String(length=200), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("query", sa.String(length=500), nullable=True),
        sa.Column("reliability", sa.Float(), nullable=False),
        sa.Column("signals", sa.JSON(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "url", name="uq_source_candidate_url"),
    )
    with op.batch_alter_table("research_sources", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_research_sources_candidate_id"), ["candidate_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("research_sources", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_research_sources_candidate_id"))

    op.drop_table("research_sources")
    with op.batch_alter_table("research_queue", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_research_queue_research_status"))
        batch_op.drop_index("ix_queue_period_order")

    op.drop_table("research_queue")
    with op.batch_alter_table("research_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_research_events_created_at"))
        batch_op.drop_index(batch_op.f("ix_research_events_candidate_id"))

    op.drop_table("research_events")
    with op.batch_alter_table("recommendation_history", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_recommendation_history_recommended_at"))
        batch_op.drop_index("ix_rec_user_movie")

    op.drop_table("recommendation_history")
    with op.batch_alter_table("watchlist", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_watchlist_status"))
        batch_op.drop_index(batch_op.f("ix_watchlist_movie_id"))

    op.drop_table("watchlist")
    op.drop_table("research_cursor")
    with op.batch_alter_table("rejected_movies", schema=None) as batch_op:
        batch_op.drop_index("ix_rejected_user_movie")

    op.drop_table("rejected_movies")
    with op.batch_alter_table("reference_movies", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reference_movies_movie_id"))

    op.drop_table("reference_movies")
    with op.batch_alter_table("preference_rules", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_preference_rules_rule_type"))

    op.drop_table("preference_rules")
    with op.batch_alter_table("movie_traits", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_movie_traits_trait"))
        batch_op.drop_index(batch_op.f("ix_movie_traits_movie_id"))

    op.drop_table("movie_traits")
    with op.batch_alter_table("movie_feedback", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_movie_feedback_movie_id"))
        batch_op.drop_index("ix_feedback_user_movie")

    op.drop_table("movie_feedback")
    with op.batch_alter_table("movie_aliases", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_movie_aliases_normalized_alias"))
        batch_op.drop_index(batch_op.f("ix_movie_aliases_movie_id"))

    op.drop_table("movie_aliases")
    with op.batch_alter_table("franchise_dependencies", schema=None) as batch_op:
        batch_op.drop_index("ix_franchise_name")

    op.drop_table("franchise_dependencies")
    with op.batch_alter_table("candidate_movies", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_candidate_movies_research_status"))

    op.drop_table("candidate_movies")
    with op.batch_alter_table("actor_preferences", schema=None) as batch_op:
        batch_op.drop_index("ix_actor_pref_name")

    op.drop_table("actor_preferences")
    op.drop_table("users")
    with op.batch_alter_table("movies", schema=None) as batch_op:
        batch_op.drop_index("ix_movies_release_date")
        batch_op.drop_index("ix_movies_normalized_title_year")
        batch_op.drop_index(batch_op.f("ix_movies_normalized_title"))

    op.drop_table("movies")
