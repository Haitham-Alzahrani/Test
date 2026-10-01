# MRIS — Movie Recommendation Intelligence System

A local, personal movie recommender that **learns one user's taste** and does **systematic,
evidence-based research** before suggesting anything. It is built for one viewer (Haitham) whose
taste is precise: strong story, strong acting, an opening that starts immediately, continuous
events and tension, crime / rescue / survival / pursuit / heist / disaster stories in modern
settings, strong production, English-language. Slow openings, talky films, sci-fi/supernatural,
franchise-dependent sequels, military/political stories and shaky-cam action are filtered out
**before** anything is shown.

Why it beats an ordinary chat:

* **Persistent structured memory** (SQLite): watched films and exact feedback, references,
  rejections *with reasons*, watch-later, learned weights/penalties, every recommendation shown.
* **Deterministic filtering** — hard exclusions and a "never recommend again" blocklist.
* **Research with receipts** — every judgement comes from stored sources (URL + quote + matched
  phrase). Missing evidence lowers confidence; it is never invented.
* **Opening-first scoring** — the first 10–15 minutes carry the largest weight and penalties.
* **A real cursor** — "continue" / «اكمل» resumes at the exact next candidate (year → month →
  release category → date), never jumps around, never restarts.
* **Learning from every message** — Arabic or English feedback becomes structured traits, weights
  and penalties.

## Quick start

```bash
cd mris
uv venv -p 3.12 .venv && source .venv/bin/activate      # or: python3.12 -m venv .venv
uv pip install -e ".[dev]"                               # or: pip install -e ".[dev]"
cp .env.example .env                                     # add API keys (optional, see below)
mris init                                                # migrations + Haitham's initial profile
mris status
mris continue                                            # or: mris say "اكمل"
mris serve                                               # dashboard at http://127.0.0.1:8765
```

### Providers (all optional)

| Variable | Used for |
|---|---|
| `MRIS_TMDB_API_KEY` | Monthly discovery, verified metadata (language, countries, genres, runtime, cast, director, collection/sequel info, budget, trailer, release type), TMDb user reviews |
| `MRIS_OMDB_API_KEY` | IMDb / Rotten Tomatoes / Metacritic ratings |
| `MRIS_SEARCH_PROVIDER` = `brave` or `tavily` + its key | Professional reviews, audience reaction, opening/pacing, acting, camera-work, franchise questions |

Without keys, MRIS still works as the taste memory and accepts manually supplied evidence
(`mris research add-evidence`) — see `CLAUDE.md` for using Claude Code as the researcher.

## CLI

```text
mris init | status | continue [--year 2025] | search [--title T --explain | --year Y --month M]
mris recommend [--count 1] [--score]
mris feedback "Mutiny" --rating loved --notes "Excellent acting, story and event progression"
mris say "شاهدته وأعجبني جدًا"          # natural language: اكمل · كان متوسط · ما عجبني · ضعه للمشاهدة لاحقًا · لا يعجبني الممثلين
mris watchlist add "Beast" --year 2026 | list | remove
mris rejected list | add | remove | franchise "John Wick"     # shown only when you ask
mris history
mris profile | profile set-rule penalty slow_opening 25 | profile exclusion science_fiction --disable | profile language en
mris database info | migrate | vacuum | export
mris backup
mris research queue | pending | add-candidate | add-evidence | explain | evaluate | rescore | retry | events | cursor
mris serve
```

## API (FastAPI, `mris serve`, docs at `/docs`)

`GET /health` · `GET /movies` · `GET /movies/{id}` · `GET /recommendations` · `POST /feedback` ·
`POST /watchlist` · `GET /watchlist` · `GET /preferences` · `GET /research/status` ·
`POST /research/continue` · `POST /message`

## Web dashboard

Dashboard (watched / loved / liked / medium / disliked / watch-later / rejected counts, cursor
position, last recommendation, message box) · Movies · Watchlist · Rejected · References ·
Preferences · Research Queue · Recommendation History. Arabic, right-to-left, light/dark.

## Development

```bash
pytest                       # 61 tests: parser, evidence, scoring, providers (mocked HTTP), migrations, research flow, API, CLI
ruff check src tests && ruff format --check src tests
```

Docs: [`docs/architecture.md`](docs/architecture.md) · [`docs/database.md`](docs/database.md) ·
[`docs/recommendation_engine.md`](docs/recommendation_engine.md) ·
[`docs/research_methodology.md`](docs/research_methodology.md)
