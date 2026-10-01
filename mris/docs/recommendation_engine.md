# Recommendation engine

## Assessment fields (stored on `candidate_movies`)

| Model | Fields |
|---|---|
| Opening | `opening_score`, `opening_confidence`, `opening_evidence` (quotes + URLs), `opening_event_start_minutes` |
| Story progression | `story_clarity`, `story_progression`, `event_continuity`, `plot_coherence`, `dialogue_to_event_ratio`, `tension_continuity`, `pacing`, `slow_burn` |
| Acting / cast | `cast_strength` (TMDb popularity of the top-billed cast = *recognisability*, blended with review evidence), `acting_quality`, `character_credibility` |
| Production | `production_quality` (review evidence 65 % + budget 35 %), `cinematography_quality`, `action_clarity`, `camera_stability`, `visual_quality` |
| Realism | `realism`, `internal_logic`, `exaggeration_level` |

Each value is `(positive + 0.5) / (positive + negative + 1)` over reliability-weighted evidence, or
`NULL` when there is none. Opening quality is never derived from genre or rating.

## Score (0–100)

Weights (editable, learned): opening 20 · story quality 15 · story progression 15 · acting/cast 10 ·
pacing/event continuity 15 · production 10 · tension/action 10 · reference similarity 5.
Unknown dimensions contribute the neutral value 0.5 (and reduce confidence).

Penalties (full for strong evidence, half for moderate): slow opening −20 · excessive dialogue −15 ·
confusing story −20 · weak cast −15 · franchise dependency −20 · chaotic camera −10 (Ambulance) ·
low production −12 (Clutch) · irrational plotting −12 · generic high concept −6 (Carry-On) ·
non-English −15 · weak ratings −10 · negative-reference similarity −10 · potential cast mismatch −8.

## Hard exclusions (automatic reject, each switchable)

Sci-fi, supernatural, fantasy, historical / pre-2000 setting, Korean / Indian / Asian-language /
Spanish-language productions, documentary, musical, military/war, political, franchise-required,
slow-burn (≥2 sources), weak opening (strong evidence), dialogue-dominated, animation, plus the
"never again" set: watched, rejected, medium-rated, on watchlist, declined, rejected franchise.

Gunfire, violence, confined locations and exaggeration are **not** exclusions. "Ex-soldier" heroes
in civilian stories are not "military-focused" (only explicit war/military-operation markers are).

## Confidence

* **HIGH** – metadata verified, opening evidence HIGH/MEDIUM, ≥5 of 7 quality dimensions evidenced,
  ≥3 independent domains, ≥1 professional review.
* **MEDIUM** – metadata verified, some opening evidence, ≥3 dimensions, ≥2 domains.
* **LOW** – otherwise.

## Decision

1. Any hard exclusion → `rejected` (stored in `rejected_movies` with reasons).
2. Score < reject threshold (55) with MEDIUM+ confidence and ≥4 known dimensions → `rejected`.
3. HIGH confidence and score ≥ pass threshold (75) → `passed` (eligible to be shown).
4. Not HIGH → `insufficient_evidence` (kept; research continues elsewhere).
5. Otherwise → `borderline` (never shown).

## Reference similarity

Candidates get a trait vector (themes from overview/keywords + traits derived from strong/weak
assessment values + flags). It is compared with each reference's vector using a weighted Jaccard
where traits the user cares about weigh more. A reference counts only when **≥3 traits** are shared,
so "crime thriller" alone never makes a film similar to *The Town*. Similarity to disliked/medium
films reduces the dimension and can add a penalty.

## Learning

| Feedback | Effect |
|---|---|
| loved / excellent | affinity +0.10 for named positive traits, matching dimension weight +0.5, small affinity boost for the film's other traits, added as a reference |
| liked / good | same with smaller steps |
| medium | affinity −0.03 for the film's traits (pattern not enough), named weaknesses' penalties +1 |
| disliked | named reasons' penalties +2 (max 35) and affinity −0.1; other traits −0.02 |
| "لا يعجبني الممثلين" | movie-scoped dislike of the two leads (universal only if said explicitly), title rejected (`user_cast`) |
| "لا اريد شي ميت" | avoid low energy / low production / weak cast / indie feeling (affinity −0.15, penalties +2) |

Run `mris research rescore` to re-evaluate stored candidates with the updated model.

## Output

One recommendation by default, in Arabic: title, up to five evidence-backed strengths, the closest
references, and at most one caveat. No scores, no rejected titles, no internal reasoning unless
requested (`--score`, `mris research explain`).
