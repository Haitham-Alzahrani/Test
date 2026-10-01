# Research methodology

## Search order (never random)

1. Years from `MRIS_SEARCH_START_YEAR` (2026) down to `MRIS_SEARCH_END_YEAR`.
2. Inside a year: January → December (future months are skipped).
3. Inside a month: TMDb discovery (≥ `MRIS_MIN_VOTE_COUNT` votes, runtime ≥ 75 min), each candidate
   classified as **theatrical** (US wide release) → **streaming** (digital premiere) → **wide**
   (theatrical outside the US) → **independent** (limited only), then sorted by release date.
4. Each candidate goes through the pipeline; the cursor is committed after every one.
5. A month with no passing candidate → next month; a year → next year; until a strong candidate is
   found or the range is exhausted. The per-run cap (`MRIS_MAX_CANDIDATES_PER_RUN`) only pauses; the
   next `continue` resumes at the exact next candidate.

## Pipeline per candidate

| Step | What happens | Stored as |
|---|---|---|
| 1 | Discovery (TMDb month / manual queue / explicit request) | `research_queue`, event |
| – | Blocklist gate (watched, rejected, medium, watchlist, declined, rejected franchise) — no research spent | `blocked` |
| 2 | Verify title, year, release date, language, countries, genres, runtime, cast, director, collection, budget, trailer | `movies`, metadata source |
| – | Metadata-level hard exclusions (genre, language, setting, sci-fi/supernatural markers) — no web calls | `rejected_movies` |
| 3 | Professional reviews query | `research_sources` |
| 4 | Audience reaction: TMDb user reviews + discussion query; OMDb ratings | sources, `movies.ratings` |
| 5 | Opening / pacing query (slow start, opening scene, first act) | sources |
| 6 | Story clarity / predictability query | sources |
| 7 | Acting / performances query | sources |
| 8 | Cinematography / action-camera query | sources |
| 9 | Franchise dependency query (only for collections / sequel keywords) | sources |
| 10 | Compare with positive references and disliked/medium films | `similar_references` |
| 11 | Hard exclusions with evidence (franchise-required, slow-burn, weak opening, dialogue-dominated) | `hard_exclusion_reason` |
| 12 | Score, penalties, confidence | `score_breakdown` |
| 13 | Decision; only `passed` can be shown | `research_status`, `decision_reason` |

Only results whose title/snippet/page actually mention the film's title are used. Pages are fetched
(once per domain per candidate) when `MRIS_FETCH_PAGES=true`; only short excerpts are stored.

## Reading evidence

`research/lexicon.py` holds the phrases this user's taste depends on — "starts immediately",
"wastes no time", "gripping from the start", "slow start", "takes a while to get going", "lengthy
setup", "slow first act", "talky", "shaky cam", "you need to have seen…", "works as a standalone"…
Matches are negation-aware within the clause ("not a slow start" is positive). Phrases such as
"takes 40 minutes before anything happens" set `opening_event_start_minutes`; above 15 minutes the
opening is treated as slow.

Evidence is weighted by source reliability (major publications ≈ 0.9–1.0, IMDb/Letterboxd/Reddit
≈ 0.6–0.7, unknown sites 0.45) and a phrase repeated on one page counts once. Consensus means
**distinct domains** agreeing. A high rating never overrides repeated "slow first half" comments; a
modest rating with repeated "starts immediately and never lets up" comments is valued.

## Without API keys

MRIS never invents research. Without providers you can:

```bash
mris research add-candidate "Title" --year 2026 --month 3
mris research add-evidence "Title" --year 2026 --url https://variety.com/... --text "verbatim review text"
mris research pending      # shows the exact searches still needed per candidate
```

`add-evidence` runs the same analysis and re-scores immediately. This is how an AI agent with its own
web-search tool (e.g. Claude Code) can act as the research provider — see `CLAUDE.md`.
