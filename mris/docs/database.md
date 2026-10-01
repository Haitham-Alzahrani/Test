# Database

SQLite (`data/mris.db` by default) in WAL mode with foreign keys enforced. The schema is created and
evolved **only** by Alembic migrations in `migrations/versions/`. `mris init`, `mris database migrate`
and every CLI command apply pending migrations automatically.

Backups: `mris backup` (or `scripts/backup_db.py`) uses the SQLite online-backup API, so it is safe
while the API server is running. The newest `MRIS_BACKUP_KEEP` files are kept in `MRIS_BACKUP_DIR`.

## Tables

| Table | Purpose | Key columns |
|---|---|---|
| `users` | Profile (name, languages, profile JSON with rules/lessons). | `name` unique |
| `movies` | One row per title. Created from user mentions or TMDb; verified metadata is written back. | `normalized_title`+`year` index, `tmdb_id` / `imdb_id` unique, `metadata_verified` |
| `movie_aliases` | Alternative titles (e.g. "Terminal List Season 1"). | FK `movie_id`, unique (`movie_id`,`normalized_alias`) |
| `movie_feedback` | Every feedback event (history kept; the latest per movie is authoritative). | `rating_label`, `rating_value`, `positive_traits`, `negative_traits`, `importance_for_learning`, `status` |
| `reference_movies` | Positive references and their importance. | unique (`user_id`,`movie_id`) |
| `movie_traits` | Trait vectors per movie, by source (`user` > `seed` > `metadata` > `research`). | unique (`movie_id`,`trait`,`source`) |
| `watchlist` | Watch-later list. | `status` (`watch_later` / `watched` / `removed`) |
| `rejected_movies` | Permanent rejections (user, trailer/cast, research pipeline) with reason, date, source and confidence. Never shown in normal output. | FK `movie_id` |
| `candidate_movies` | One researched candidate with **every assessed field** (opening model, story progression model, acting model, production model, realism model, franchise dependency, similarity, risks, strengths, score breakdown, confidence, decision). | `movie_id` unique, `research_status` |
| `research_queue` | Candidates per (year, month) in deterministic order. | unique (`year`,`month`,`movie_id`), index (`year`,`month`,`sort_order`) |
| `research_sources` | Each source consulted: URL, domain, publisher, type, reliability, snippet, query and the matched signals (phrase + sentence). | unique (`candidate_id`,`url`) |
| `research_events` | Step-by-step research log. | `candidate_id`, `step`, `created_at` |
| `research_cursor` | Exact resume position: year, month, last queue item/candidate, range, counters, status. | `user_id` unique |
| `preference_rules` | Weights, penalties, exclusion switches, thresholds and learned trait affinities. | unique (`user_id`,`rule_type`,`key`) |
| `actor_preferences` | Cast likes/dislikes; `scope` = `movie` (default) or `universal` (only when explicitly said). | `normalized_name` index |
| `franchise_dependencies` | Known franchise dependencies and rejected franchises. | `franchise_name` index |
| `recommendation_history` | Every recommendation shown, with score, reason, research version and the user's response. | (`user_id`,`movie_id`) index |

## Rating labels

`loved`, `excellent`, `liked`, `good` (positive) · `medium`, `average`, `medium_low` (medium – never
recommended again) · `disliked` (negative).

## Adding a migration

```bash
# edit src/mris/models/tables.py, then
MRIS_DB_PATH=/tmp/scratch.db alembic upgrade head
MRIS_DB_PATH=/tmp/scratch.db alembic revision --autogenerate -m "describe change"
pytest tests/integration/test_migrations.py
```
