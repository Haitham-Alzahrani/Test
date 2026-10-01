-- movie_memory.sqlite — schema + historical seed.
-- Used ONCE to build the database. After that, movie_memory.sqlite is the source of truth;
-- do NOT re-run this on an existing database (it would wipe learned memory).

PRAGMA foreign_keys = ON;

-- ============================================================
-- SCHEMA
-- ============================================================

-- Every title the agent knows about (watched, rejected, watchlist, candidates, researched).
CREATE TABLE movies (
    id              INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    year            INTEGER,
    kind            TEXT NOT NULL DEFAULT 'movie',      -- movie | series
    status          TEXT NOT NULL,                      -- watched | rejected | watchlist | candidate | needs_reevaluation
                                                        -- | recommended | declined | researched_failed
    rating          TEXT,                               -- loved | excellent | liked | good | medium | medium_low
                                                        -- | average | disliked | bad | stopped
    rating_score    INTEGER,                            -- rough 1–10 for ordering
    block_recommend INTEGER NOT NULL DEFAULT 1,         -- 1 = never offer as a fresh recommendation
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (title, year)
);

-- Every user statement about a movie, with the extracted meaning.
CREATE TABLE feedback (
    id         INTEGER PRIMARY KEY,
    movie_id   INTEGER NOT NULL REFERENCES movies(id),
    date       TEXT NOT NULL DEFAULT (date('now')),
    source     TEXT NOT NULL DEFAULT 'user',            -- user | seed
    raw_text   TEXT,                                    -- the user's words, verbatim when available
    rating     TEXT,
    positives  TEXT,                                    -- comma-separated trait tags
    negatives  TEXT,                                    -- comma-separated trait tags
    learning   TEXT                                     -- what this teaches about the user's taste
);

-- Taste rules, hard exclusions, scoring weights, penalties, learned adjustments.
CREATE TABLE preferences (
    key          TEXT PRIMARY KEY,
    category     TEXT NOT NULL,                         -- want | avoid | hard_exclusion | rule
                                                        -- | score_weight | penalty | search
    description  TEXT NOT NULL,
    weight       REAL,                                  -- importance 1–5 for want/avoid/rule; % for score_weight; points for penalty
    learned_from TEXT,                                  -- movie(s) that created/strengthened this rule
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Reference movies (positive models to match, negative models to avoid).
-- (Named reference_movies because REFERENCES is an SQL reserved word.)
CREATE TABLE reference_movies (
    movie_id  INTEGER PRIMARY KEY REFERENCES movies(id),
    polarity  TEXT NOT NULL,                            -- positive | negative
    strength  INTEGER NOT NULL,                         -- 1–5 (5 = strongest signal)
    traits    TEXT NOT NULL,                            -- comma-separated trait tags
    notes     TEXT
);

-- Titles the user explicitly asked to keep for later.
CREATE TABLE watchlist (
    movie_id   INTEGER PRIMARY KEY REFERENCES movies(id),
    added_date TEXT NOT NULL DEFAULT (date('now')),
    notes      TEXT
);

-- Research done on candidates (including failed ones, so they are never re-researched needlessly).
CREATE TABLE research (
    id             INTEGER PRIMARY KEY,
    movie_id       INTEGER NOT NULL REFERENCES movies(id),
    date           TEXT NOT NULL DEFAULT (date('now')),
    search_year    INTEGER,
    search_month   INTEGER,
    release_date   TEXT,
    runtime_min    INTEGER,
    language       TEXT,
    country        TEXT,
    cast_names     TEXT,
    story          TEXT,
    opening        TEXT,                                -- first 10–15 minutes assessment
    pacing         TEXT,
    progression    TEXT,
    acting         TEXT,
    production     TEXT,
    cinematography TEXT,
    action_tension TEXT,
    logic          TEXT,
    standalone     TEXT,
    audience       TEXT,
    critics        TEXT,
    similar_to     TEXT,                                -- positive/negative reference similarity
    score          REAL,                                -- internal only, never shown unless asked
    verdict        TEXT NOT NULL,                       -- recommend | reject | hold
    reject_reason  TEXT,
    sources        TEXT
);

-- Persistent search cursor (single row, id = 1).
CREATE TABLE search_state (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    year             INTEGER NOT NULL,
    month            INTEGER NOT NULL,
    last_candidate   TEXT,
    last_action      TEXT,
    last_search_date TEXT,
    range_end_year   INTEGER NOT NULL,                  -- oldest year in the configured search range
    notes            TEXT
);

-- Every recommendation ever shown and what happened to it.
CREATE TABLE recommendation_history (
    id            INTEGER PRIMARY KEY,
    movie_id      INTEGER NOT NULL REFERENCES movies(id),
    date          TEXT NOT NULL DEFAULT (date('now')),
    confidence    TEXT,                                 -- high | very_high
    outcome       TEXT NOT NULL DEFAULT 'shown',        -- shown | watched | declined | watchlisted
    user_response TEXT,
    notes         TEXT
);

-- Convenience: everything that must never be offered as a fresh recommendation.
CREATE VIEW blocked_titles AS
    SELECT id, title, year, status, rating
    FROM movies
    WHERE block_recommend = 1;

-- ============================================================
-- SEED — MOVIES
-- ============================================================

INSERT INTO movies (title, year, kind, status, rating, rating_score, block_recommend, notes) VALUES
-- Positive references (watched)
('Mutiny',              2026, 'movie',  'watched',  'loved',      10, 1, 'One of the strongest current signals. Loved: acting, story, events, event progression all excellent.'),
('Runner',              2026, 'movie',  'watched',  'loved',      10, 1, 'Loved very much. Very fast, immediate danger, continuous movement.'),
('Last Breath',         2025, 'movie',  'watched',  'excellent',   9, 1, 'Excellent / extremely positive. One of the strongest survival references.'),
('Fuze',                2026, 'movie',  'watched',  'liked',       8, 1, 'Liked. Modern crime heist, movement, chaos, strong pacing.'),
('The Town',            2010, 'movie',  'watched',  'excellent',   9, 1, 'Excellent. Crime/heist, strong acting and story, realistic action.'),
('Taken',               2008, 'movie',  'watched',  'liked',       8, 1, 'Liked very much. Rescue, pursuit, revenge, clear objective, immediate conflict.'),
('Man on Fire',         2004, 'movie',  'watched',  'excellent',   9, 1, 'Excellent.'),
('Nobody',              2021, 'movie',  'watched',  'excellent',   9, 1, 'Excellent.'),
('The Equalizer',       2014, 'movie',  'watched',  'excellent',   9, 1, 'Excellent.'),
('Wrath of Man',        2021, 'movie',  'watched',  'excellent',   9, 1, 'Excellent.'),
('The Accountant',      2016, 'movie',  'watched',  'liked',       8, 1, 'Liked.'),
('Law Abiding Citizen', 2009, 'movie',  'watched',  'liked',       8, 1, 'Liked.'),
('Deepwater Horizon',   2016, 'movie',  'watched',  'liked',       8, 1, 'Liked. Offshore industrial disaster, fire/explosion, evacuation, purposeful action.'),
-- Watched — medium / good / disliked
('The Rip',             2026, 'movie',  'watched',  'medium',      5, 1, 'Medium. Never recommend again unless explicitly requested.'),
('Carry-On',            2024, 'movie',  'watched',  'medium',      5, 1, 'Medium. Never recommend again unless explicitly requested. Learning: "ordinary person + criminal situation" alone is not enough; execution must be strong.'),
('The Amateur',         2025, 'movie',  'watched',  'disliked',    2, 1, 'Disliked. Very slow; user was bored within the first ten minutes. Strong negative reference for slow openings.'),
('Den of Thieves',      2018, 'movie',  'watched',  'bad',         1, 1, 'Bad / disliked. Do not recommend.'),
('Ambulance',           2022, 'movie',  'watched',  'average',     5, 1, 'Average. Disliked the filming/cinematography — avoid excessively shaky or visually chaotic camera work.'),
('Crime 101',           2026, 'movie',  'watched',  'medium_low',  4, 1, 'Acceptable / medium-low. Did not take his breath away. Do not prioritize similar slow/less intense pacing.'),
('Twisters',            2024, 'movie',  'watched',  'average',     5, 1, 'Average. Do not recommend again.'),
('The Lost Bus',        2025, 'movie',  'watched',  'good',        7, 1, 'Good / 7 out of 10. Positive but not top-tier. Not a fresh discovery unless explicitly requested.'),
('Dead of Winter',      2025, 'movie',  'watched',  'good',        7, 1, 'Good. Do not recommend again as a fresh discovery.'),
('A Working Man',       2025, 'movie',  'watched',  'good',        7, 1, 'Good. Do not recommend again as a fresh discovery.'),
('Plane',               2023, 'movie',  'watched',  'good',        7, 1, 'Good. Do not recommend again as a fresh discovery.'),
('The Impossible',      2012, 'movie',  'watched',  'bad',         1, 1, 'Bad / disliked. Learning: disaster movies are NOT automatically good — the danger itself must create sustained tension.'),
('The Night Manager',   2016, 'series', 'watched',  'liked',       7, 1, 'Liked eventually. Negative: too much dialogue. Dialogue is acceptable only when it keeps the story moving.'),
('The Terminal List (Season 1)', 2022, 'series', 'watched', 'stopped', 2, 1, 'Boring / stopped watching. Do not recommend.'),
-- Rejected (not watched in full)
('Reckless',            2026, 'movie',  'rejected', NULL,       NULL, 1, 'Rejected after watching the trailer: the actors did not appeal to the user. Candidate-specific — do NOT globally ban these actors.'),
('Ballerina',           2025, 'movie',  'rejected', NULL,       NULL, 1, 'Rejected: depends on the John Wick universe. Standalone clarity is important.'),
('Clutch',              2025, 'movie',  'rejected', NULL,       NULL, 1, 'Rejected: felt "dead" / weak / low-energy. User does not want weak-looking low-production movies.'),
-- Watch later (explicit user requests)
('Beast',               2026, 'movie',  'watchlist', NULL,      NULL, 1, 'User explicitly asked to watch later. Not a new recommendation.'),
('Hotel Mumbai',        2018, 'movie',  'watchlist', NULL,      NULL, 1, 'User explicitly asked to put it on the list.'),
('Fight or Flight',     2025, 'movie',  'watchlist', NULL,      NULL, 1, 'User watched ~first 5 minutes; initial impression: more comedic than thrilling. NOT rejected — user explicitly wanted it saved for later.'),
-- Historical candidates: must be re-evaluated against current preferences before ever being shown
('Shelter',             2026, 'movie',  'needs_reevaluation', NULL, NULL, 1, 'Historical candidate/watchlist. Some reviews indicated slower startup. Do not auto-recommend; full re-evaluation required before showing.'),
('Send Help',           2026, 'movie',  'needs_reevaluation', NULL, NULL, 1, 'Historical candidate. Do not auto-recommend; full re-evaluation required before showing.');

-- ============================================================
-- SEED — REFERENCE MOVIES
-- ============================================================

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 5, 'excellent_acting,excellent_story,excellent_event_progression,clear_plot,strong_action,crime,pursuit,strong_production,good_opening',
       'One of the strongest reference movies. User: "اعجبني لان التمثيل والقصه والاحداث والتسلسل ممتازه"'
FROM movies WHERE title = 'Mutiny' AND year = 2026;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 5, 'very_fast,immediate_danger,continuous_movement,rescue,pursuit,high_tension,modern,entertaining', 'Loved very much.'
FROM movies WHERE title = 'Runner' AND year = 2026;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 5, 'realistic_survival,offshore,rescue,oxygen_time_pressure,disaster,sustained_danger,serious_tone,strong_tension',
       'One of the strongest survival references. Proves enclosed/offshore settings work when danger is continuous.'
FROM movies WHERE title = 'Last Breath' AND year = 2025;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 3, 'modern,crime,heist,movement,chaos,strong_pacing', 'Liked.'
FROM movies WHERE title = 'Fuze' AND year = 2026;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 4, 'crime,heist,strong_acting,strong_story,realistic_action', 'Excellent.'
FROM movies WHERE title = 'The Town' AND year = 2010;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 4, 'rescue,pursuit,revenge,clear_objective,immediate_conflict', 'Liked very much.'
FROM movies WHERE title = 'Taken' AND year = 2008;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 4, 'rescue,revenge,protection,strong_acting,crime', 'Excellent.'
FROM movies WHERE title = 'Man on Fire' AND year = 2004;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 4, 'ordinary_man_with_hidden_skills,crime,revenge,fast_pacing,entertaining', 'Excellent.'
FROM movies WHERE title = 'Nobody' AND year = 2021;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 4, 'protection,crime,revenge,strong_acting,clear_objective', 'Excellent.'
FROM movies WHERE title = 'The Equalizer' AND year = 2014;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 4, 'crime,heist,revenge,tension,strong_acting', 'Excellent.'
FROM movies WHERE title = 'Wrath of Man' AND year = 2021;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 3, 'crime,action,strong_acting', 'Liked.'
FROM movies WHERE title = 'The Accountant' AND year = 2016;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 3, 'crime,revenge,tension,clear_objective', 'Liked.'
FROM movies WHERE title = 'Law Abiding Citizen' AND year = 2009;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'positive', 4, 'offshore,industrial_disaster,fire_explosion,evacuation,survival,purposeful_action,realistic_danger', 'Liked.'
FROM movies WHERE title = 'Deepwater Horizon' AND year = 2016;

-- Negative references
INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'negative', 5, 'slow_opening,long_setup,low_initial_engagement,slow_pacing', 'Bored within the first ten minutes. Strongest slow-opening warning.'
FROM movies WHERE title = 'The Amateur' AND year = 2025;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'negative', 4, 'dead_feel,low_energy,weak_production,weak_cinematic_presence', 'Felt dead.'
FROM movies WHERE title = 'Clutch' AND year = 2025;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'negative', 4, 'franchise_dependency', 'Depends on John Wick universe.'
FROM movies WHERE title = 'Ballerina' AND year = 2025;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'negative', 3, 'cast_did_not_appeal', 'Candidate-specific cast rejection. Not a global actor ban.'
FROM movies WHERE title = 'Reckless' AND year = 2026;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'negative', 3, 'premise_without_strong_execution,ordinary_person_criminal_situation', 'Premise alone is not enough.'
FROM movies WHERE title = 'Carry-On' AND year = 2024;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'negative', 4, 'disaster_without_sustained_tension', 'Disaster genre is not automatically good.'
FROM movies WHERE title = 'The Impossible' AND year = 2012;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'negative', 3, 'shaky_camera,visually_chaotic_cinematography', 'Disliked the filming.'
FROM movies WHERE title = 'Ambulance' AND year = 2022;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'negative', 3, 'not_breathtaking,less_intense_pacing', 'Did not take his breath away.'
FROM movies WHERE title = 'Crime 101' AND year = 2026;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'negative', 3, 'disliked_overall', 'Bad / disliked.'
FROM movies WHERE title = 'Den of Thieves' AND year = 2018;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'negative', 2, 'too_much_dialogue', 'Liked eventually, but dialogue load was a negative.'
FROM movies WHERE title = 'The Night Manager' AND year = 2016;

INSERT INTO reference_movies (movie_id, polarity, strength, traits, notes)
SELECT id, 'negative', 3, 'boring,military_focus', 'Stopped watching.'
FROM movies WHERE title = 'The Terminal List (Season 1)' AND year = 2022;

-- ============================================================
-- SEED — WATCHLIST
-- ============================================================

INSERT INTO watchlist (movie_id, added_date, notes)
SELECT id, '2026-10-01', 'Explicit user request. Not a new recommendation.' FROM movies WHERE title = 'Beast' AND year = 2026;
INSERT INTO watchlist (movie_id, added_date, notes)
SELECT id, '2026-10-01', 'User explicitly asked to put it on the list.' FROM movies WHERE title = 'Hotel Mumbai' AND year = 2018;
INSERT INTO watchlist (movie_id, added_date, notes)
SELECT id, '2026-10-01', 'Watched ~5 min; seemed more comedic than thrilling. Saved for later by explicit request — not rejected.' FROM movies WHERE title = 'Fight or Flight' AND year = 2025;

-- ============================================================
-- SEED — FEEDBACK (historical)
-- ============================================================

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', 'Mutiny عجبني لان التمثيل والقصه والاحداث والتسلسل ممتازه', 'loved',
       'acting,story,events,event_progression', NULL,
       'Increase importance of acting, story, event progression, logical sequence, strong production.'
FROM movies WHERE title = 'Mutiny';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', NULL, 'loved', 'very_fast,immediate_danger,continuous_movement,rescue,pursuit,high_tension,modern,entertaining', NULL,
       'Fast, immediately dangerous, continuous-movement stories are top-tier.'
FROM movies WHERE title = 'Runner';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', NULL, 'excellent', 'realistic_survival,offshore,rescue,time_pressure,sustained_danger,serious_tone', NULL,
       'Enclosed/offshore survival works when danger is sustained.'
FROM movies WHERE title = 'Last Breath';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', 'هذا بطيء جدا لم يعجبني مللت منه من اول عشر دقايق', 'disliked',
       NULL, 'slow_opening,low_initial_engagement,slow_pacing',
       'Increase penalty for slow openings, long setup, low initial engagement. A high rating does not override this.'
FROM movies WHERE title = 'The Amateur';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', NULL, NULL, NULL, 'cast_did_not_appeal',
       'Increase importance of appealing/convincing cast. Candidate-specific; not a global actor ban.'
FROM movies WHERE title = 'Reckless';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', NULL, NULL, NULL, 'dead_feel,low_energy,weak_production',
       'Increase importance of production quality, energy, cinematic presence.'
FROM movies WHERE title = 'Clutch';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', NULL, NULL, NULL, 'franchise_dependency',
       'Increase penalty for franchise dependency. Standalone stories only.'
FROM movies WHERE title = 'Ballerina';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', NULL, 'medium', NULL, 'weak_execution',
       '"Ordinary person + criminal situation" alone is not enough; execution must be strong.'
FROM movies WHERE title = 'Carry-On';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', NULL, 'bad', NULL, 'disaster_without_sustained_tension',
       'Disaster movies are not automatically good; the danger must create sustained tension.'
FROM movies WHERE title = 'The Impossible';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', NULL, 'average', NULL, 'shaky_camera,chaotic_cinematography',
       'Avoid excessively shaky or visually chaotic camera work.'
FROM movies WHERE title = 'Ambulance';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', NULL, 'medium_low', NULL, 'not_breathtaking,less_intense_pacing',
       'Do not prioritize slow/less intense pacing.'
FROM movies WHERE title = 'Crime 101';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', NULL, 'liked', NULL, 'too_much_dialogue',
       'Dialogue is acceptable only when it keeps the story moving.'
FROM movies WHERE title = 'The Night Manager';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', NULL, 'stopped', NULL, 'boring',
       'Stopped watching. Do not recommend.'
FROM movies WHERE title = 'The Terminal List (Season 1)';

INSERT INTO feedback (movie_id, date, source, raw_text, rating, positives, negatives, learning)
SELECT id, '2026-10-01', 'seed', 'Watched about the first five minutes', NULL, NULL, 'seemed_comedic',
       'Initial impression only. Explicitly saved for later — not a rejection.'
FROM movies WHERE title = 'Fight or Flight';

-- ============================================================
-- SEED — PREFERENCES
-- ============================================================

INSERT INTO preferences (key, category, description, weight, learned_from) VALUES
-- What the user wants
('exciting',              'want', 'Exciting movies that feel alive', 5, NULL),
('strong_story',          'want', 'Strong, clear story', 5, 'Mutiny'),
('strong_acting',         'want', 'Strong, convincing acting; preferably well-known actors', 5, 'Mutiny, Reckless'),
('strong_opening',        'want', 'Strong opening that hooks within the first 10 minutes', 5, 'The Amateur'),
('event_progression',     'want', 'Excellent event progression: event → consequence → new problem → escalation → action → consequence → resolution', 5, 'Mutiny'),
('continuous_events',     'want', 'Continuous meaningful events, tension, movement, escalation', 5, 'Runner, Last Breath'),
('genres_core',           'want', 'Tension, action, crime, revenge, rescue, survival, pursuit, escape, heists, police action, hostage situations, protection', 5, NULL),
('disasters',             'want', 'Disasters incl. industrial/offshore disasters — only when the danger creates sustained tension', 4, 'Last Breath, Deepwater Horizon, The Impossible'),
('time_pressure',         'want', 'Time pressure', 4, 'Last Breath'),
('modern_setting',        'want', 'Modern settings', 4, NULL),
('production_quality',    'want', 'Strong production quality, energy, cinematic presence', 5, 'Clutch'),
('english_language',      'want', 'Primarily English-language productions', 4, NULL),
('standalone',            'want', 'Must make sense by itself', 5, 'Ballerina'),
('purposeful_action',     'want', 'Action with a purpose (rescue, revenge, escape, pursuit, hostage, robbery, protection, survival, crime). Gunfire is fine when it serves the story.', 4, NULL),
-- What the user avoids
('slow_opening',          'avoid', 'Slow opening, long setup, excessive exposition, long introductions, dialogue-heavy beginning, boring first 10–15 minutes. A high rating does NOT override this.', 5, 'The Amateur'),
('dead_feel',             'avoid', 'Movie that feels dead, weak, cheap, empty', 5, 'Clutch'),
('padded_slow',           'avoid', 'Slow or padded pacing', 5, 'The Amateur, Crime 101'),
('needless_complexity',   'avoid', 'Unnecessarily complicated plots', 4, NULL),
('static_dialogue',       'avoid', 'Dialogue that stops the movie. Dialogue that advances story, creates tension, explains a key situation or meaningfully develops characters is fine.', 4, 'The Night Manager'),
('shaky_camera',          'avoid', 'Excessively shaky or visually chaotic camera work', 3, 'Ambulance'),
('stupid_plotting',       'avoid', 'Stupid plotting / illogical character behavior (worse than simple exaggeration)', 5, NULL),
('obscure_low_budget',    'avoid', 'Obscure low-production movies recommended merely because the premise matches', 4, 'Clutch'),
('military_gunfire',      'avoid', 'Military/war-style gunfire where shooting becomes the whole movie without a clear civilian objective', 4, 'The Terminal List'),
('premise_only',          'avoid', 'Good premise without strong execution ("ordinary person + criminal situation" is not enough by itself)', 4, 'Carry-On'),
-- Rules / nuances
('enclosed_settings',     'rule', 'Enclosed settings (plane, ship, oil platform, train, prison, building, submarine) are ACCEPTABLE. Deciding factor: are meaningful events continuously happening? Static dialogue → reject.', 5, 'Last Breath, Deepwater Horizon'),
('realism',               'rule', 'Prefers realistic/plausible, but realism is NOT a hard requirement. Exaggeration OK if story stays coherent, characters behave logically, it is entertaining, and it does not become stupid.', 4, NULL),
('actor_rejection_scope', 'rule', 'Cast rejection is candidate-specific. Never globally ban an actor unless the user explicitly says so.', 5, 'Reckless'),
('dialogue_ok_if_moving', 'rule', 'Dialogue is not automatically bad; the problem is dialogue that stops the movie.', 4, 'The Night Manager'),
('one_at_a_time',         'rule', 'Show ONE recommendation at a time unless the user explicitly asks for a list.', 5, NULL),
('hide_failed',           'rule', 'Never show or list rejected/failed candidates. If nothing qualifies say only: "لم أجد حتى الآن مرشحًا يستحق العرض."', 5, NULL),
('no_threshold_lowering', 'rule', 'Never lower the threshold just to produce a title. Never claim 100% certainty.', 5, NULL),
('research_why',          'rule', 'Key research question: why did viewers like or dislike it? Focus on beginning, pacing, boredom, acting, story, progression, action, dialogue. Ratings alone are not enough.', 5, NULL),
-- Hard exclusions
('excl_scifi',            'hard_exclusion', 'Science fiction', NULL, NULL),
('excl_supernatural',     'hard_exclusion', 'Supernatural', NULL, NULL),
('excl_fantasy',          'hard_exclusion', 'Fantasy', NULL, NULL),
('excl_historical',       'hard_exclusion', 'Historical / pre-2000 settings', NULL, NULL),
('excl_documentary',      'hard_exclusion', 'Documentaries', NULL, NULL),
('excl_musical',          'hard_exclusion', 'Musicals', NULL, NULL),
('excl_korean',           'hard_exclusion', 'Korean productions', NULL, NULL),
('excl_asian_language',   'hard_exclusion', 'Asian-language primary productions', NULL, NULL),
('excl_indian',           'hard_exclusion', 'Indian productions', NULL, NULL),
('excl_spanish_language', 'hard_exclusion', 'Spanish-language primary productions', NULL, NULL),
('excl_military',         'hard_exclusion', 'Military-focused stories', NULL, NULL),
('excl_war',              'hard_exclusion', 'War-focused stories', NULL, NULL),
('excl_political',        'hard_exclusion', 'Political stories', NULL, NULL),
('excl_us_politics',      'hard_exclusion', 'U.S.-politics-dependent stories', NULL, NULL),
('excl_confusing',        'hard_exclusion', 'Confusing stories', NULL, NULL),
('excl_franchise',        'hard_exclusion', 'Movies requiring knowledge of another movie/franchise/universe/previous characters/events', NULL, 'Ballerina'),
('excl_weak_opening',     'hard_exclusion', 'Very weak openings', NULL, 'The Amateur'),
('excl_very_slow',        'hard_exclusion', 'Excessively slow movies', NULL, 'The Amateur'),
('excl_dialogue_heavy',   'hard_exclusion', 'Dialogue-heavy movies where events stop', NULL, 'The Night Manager'),
('excl_weak_production',  'hard_exclusion', 'Weak / cheap / low-energy productions', NULL, 'Clutch'),
-- Internal scoring weights (%)
('w_opening',             'score_weight', 'Opening', 20, 'The Amateur'),
('w_story',               'score_weight', 'Story', 20, 'Mutiny'),
('w_progression',         'score_weight', 'Event progression', 15, 'Mutiny'),
('w_acting_cast',         'score_weight', 'Acting / cast', 15, 'Mutiny, Reckless'),
('w_pacing',              'score_weight', 'Pacing', 10, NULL),
('w_production',          'score_weight', 'Production quality', 10, 'Clutch'),
('w_action_tension',      'score_weight', 'Action / tension', 10, NULL),
-- Penalties (points)
('p_slow_opening',        'penalty', 'Slow opening', -20, 'The Amateur'),
('p_very_slow',           'penalty', 'Very slow pacing', -20, NULL),
('p_excess_dialogue',     'penalty', 'Excessive dialogue', -15, 'The Night Manager'),
('p_confusing',           'penalty', 'Confusing story', -20, NULL),
('p_weak_acting',         'penalty', 'Weak acting', -15, 'Reckless'),
('p_weak_production',     'penalty', 'Weak production', -15, 'Clutch'),
('p_franchise',           'penalty', 'Franchise dependency', -20, 'Ballerina'),
('p_stupid_behavior',     'penalty', 'Stupid character behavior', -20, NULL),
-- Search configuration
('search_order',          'search', 'Search month by month: 2026 Jan→Dec, then 2025 Jan→Dec, then 2024 and older if necessary. Skip months that have not happened yet.', NULL, NULL),
('recommend_threshold',   'search', 'Minimum internal score to show a movie (0–100 after penalties). Hard exclusions override any score.', 80, NULL);

-- ============================================================
-- SEED — SEARCH CURSOR
-- ============================================================

INSERT INTO search_state (id, year, month, last_candidate, last_action, last_search_date, range_end_year, notes)
VALUES (1, 2026, 1, NULL, 'initialized', NULL, 2015,
        'Start of systematic search. Advance month by month inside a year (Jan→Dec), then go to the previous year.');
