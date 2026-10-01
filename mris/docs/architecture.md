# Architecture

MRIS is a local, single-user Python application. All state lives in one SQLite database; every
interface (CLI, JSON API, web dashboard, natural-language messages) goes through the same
service object, so behaviour is identical everywhere.

```
            ┌──────────── cli/ (Typer) ───────────┐   ┌──── api/ (FastAPI + Jinja2 dashboard) ────┐
            └──────────────────┬──────────────────┘   └───────────────────┬───────────────────────┘
                               └──────────────► service.MRIS ◄────────────┘
                                                     │
   ┌──────────────────┬──────────────────┬───────────┴────────┬────────────────────┬────────────────┐
   │ memory/          │ research/        │ scoring/           │ recommendation/    │ search/        │
   │ parser (AR/EN)   │ engine (cursor)  │ assessment         │ blocklist          │ TMDb  (meta)   │
   │ learning         │ pipeline (13 st.)│ exclusions         │ engine             │ OMDb  (ratings)│
   │ seed             │ evidence+lexicon │ similarity         │ formatter (AR/EN)  │ Brave/Tavily   │
   │ vocabulary       │                  │ compatibility      │                    │ page fetcher   │
   └────────┬─────────┴────────┬─────────┴─────────┬──────────┴─────────┬──────────┴────────────────┘
            └──────────────────┴──── repositories/ (SQLAlchemy) ────────┘
                                          │
                               database/ (engine WAL+FK, Alembic, backup) ── SQLite
```

## Modules

| Package | Responsibility |
|---|---|
| `config.py` | `MRIS_*` settings (pydantic-settings, `.env`). Missing provider keys disable steps; nothing is guessed. |
| `database/` | Engine with `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout`; programmatic Alembic upgrades; online backups via the SQLite backup API. |
| `models/` | ORM tables (17) and enums. The schema is owned by `migrations/`; a test asserts models == migrations. |
| `repositories/` | Small query classes per aggregate; `Repos` bundles them for one session. |
| `search/` | Provider protocols and clients. `MetadataProvider` (TMDb discovery + verified details + TMDb user reviews), `RatingsProvider` (OMDb), `WebSearchProvider` (Brave or Tavily), `PageFetcher`. `sources.py` classifies domains as professional / audience and assigns reliability. |
| `research/lexicon.py` | The phrase lexicon (opening, pacing, story clarity, progression, dialogue, tension, acting, cast, production, camera, realism, franchise) + flags + metadata exclusion patterns. |
| `research/evidence.py` | Negation-aware signal extraction per sentence and the per-candidate `EvidenceSummary` (reliability-weighted, distinct-domain counting). |
| `research/pipeline.py` | The 13-step per-candidate research (see `research_methodology.md`). |
| `research/engine.py` | Systematic, resumable year→month traversal with the persistent cursor. |
| `scoring/` | Assessment fields, hard exclusions, reference similarity, 0–100 score, confidence and decision. |
| `memory/` | Natural-language feedback parsing (Arabic + English), bounded learning, seed data. |
| `recommendation/` | "Never recommend again" blocklist, selection of HIGH-confidence candidates, concise output. |
| `service.py` | Facade used by every interface. |

## Key design decisions

* **Deterministic core.** Parsing, evidence extraction, scoring and the search order are rule-based.
  The same inputs always give the same decision, and every decision can be explained from stored rows
  (`mris research explain "Title"`).
* **No fabrication.** Fields without evidence stay `NULL`; unknown dimensions count as neutral in the
  score *and* lower confidence; only HIGH confidence + score ≥ threshold is ever shown.
* **Durable progress.** The cursor and queue are committed after every candidate, so `continue` never
  restarts and a crash loses at most one candidate's work.
* **Provider-optional.** With no API keys MRIS still works as a taste memory, and research can be fed
  manually (`mris research add-evidence`) — e.g. by an AI agent that has its own web access.
* **Learning is bounded and visible.** Weights move by ±0.5 within [3, 30], penalties within [0, 35],
  affinities within [−1, 1]; all live in `preference_rules` and can be edited (`mris profile set-rule`).
