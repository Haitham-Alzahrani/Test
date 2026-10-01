"""Default taste model. These values are seeded into `preference_rules`; the live values are
always read back from the database so learning and manual edits take effect."""

from __future__ import annotations

# Positive score weights (points out of 100). Keys are scoring dimensions.
DEFAULT_WEIGHTS: dict[str, float] = {
    "opening": 20,
    "story_quality": 15,
    "story_progression": 15,
    "acting_cast": 10,
    "pacing_continuity": 15,
    "production": 10,
    "tension_action": 10,
    "reference_similarity": 5,
}

# Hard penalties (points subtracted when the flag is raised by real evidence).
DEFAULT_PENALTIES: dict[str, float] = {
    "slow_opening": 20,
    "excessive_dialogue": 15,
    "confusing_story": 20,
    "weak_cast": 15,
    "franchise_dependency": 20,
    "chaotic_camera": 10,  # learned from Ambulance (disliked filming style)
    "low_production": 12,  # learned from Clutch ("dead"/too small)
    "irrational_plotting": 12,
    "generic_high_concept": 6,  # learned from Carry-On (medium)
    "non_english": 15,
    "weak_ratings": 10,
    "negative_reference_similarity": 10,
    "potential_cast_mismatch": 8,
}

# Automatic-reject switches. Disabling one turns it off without deleting history.
DEFAULT_EXCLUSIONS: dict[str, str] = {
    "science_fiction": "Science fiction",
    "supernatural": "Supernatural / horror-fantasy elements",
    "fantasy": "Fantasy",
    "historical_setting": "Historical / period setting",
    "pre_2000_setting": "Story set before 2000",
    "excluded_language": "Korean / Indian / Asian-language / Spanish-language primary production",
    "documentary": "Documentary",
    "musical": "Musical",
    "military_war": "Military- or war-focused story",
    "political": "Political / U.S.-politics-dependent story",
    "franchise_required": "Requires knowledge of another franchise or previous films",
    "slow_burn": "Slow-burn film",
    "weak_opening": "Weak / slow opening confirmed by credible reviews",
    "dialogue_dominated": "Dominated by dialogue without event progression",
    "animation": "Animated feature (user wants live-action casts)",
    "previously_watched": "Already watched",
    "previously_rejected": "Rejected before",
    "medium_rating": "Watched and rated medium",
    "on_watchlist": "Already on the watch-later list",
    "declined_recommendation": "Recommended before and declined",
    "rejected_franchise": "Belongs to a franchise the user rejected",
}

DEFAULT_THRESHOLDS: dict[str, float] = {
    "pass_score": 75.0,
    "reject_score": 55.0,
    "max_opening_event_start_minutes": 15.0,
}

# Learned trait affinities (-1 .. +1) from the user's history (section 29 lessons).
DEFAULT_TRAIT_AFFINITIES: dict[str, tuple[float, str]] = {
    "strong_story": (0.6, "Mutiny: story + acting + event progression matter greatly"),
    "strong_acting": (0.6, "Mutiny"),
    "event_progression": (0.6, "Mutiny"),
    "strong_opening": (0.7, "The Amateur: slow openings are heavily penalised"),
    "immediate_danger": (0.5, "Runner / Taken"),
    "time_pressure": (0.5, "Last Breath"),
    "rescue": (0.4, "Last Breath / Runner / Taken"),
    "pursuit": (0.4, "Runner / Mutiny / Taken"),
    "heist": (0.4, "The Town / Fuze"),
    "crime": (0.4, "The Town / Mutiny / Fuze"),
    "revenge": (0.3, "Taken / Man on Fire"),
    "survival": (0.4, "Last Breath / Deepwater Horizon"),
    "offshore": (0.3, "Last Breath / Deepwater Horizon"),
    "industrial_disaster": (0.3, "Deepwater Horizon"),
    "ordinary_person_in_danger": (0.3, "Collateral: ordinary person caught in a criminal situation"),
    "modern_setting": (0.4, "Collateral lesson: wants modern/high-energy execution"),
    "standalone": (0.5, "Ballerina: standalone clarity is essential"),
    "strong_production": (0.5, "Clutch: production quality and cinematic presence matter"),
    "action_only": (-0.4, "Mutiny lesson: action alone is insufficient"),
    "generic_high_concept": (-0.3, "Carry-On: generic high-concept thriller is not enough"),
    "slow_opening": (-0.9, "The Amateur"),
    "excessive_dialogue": (-0.6, "The Night Manager"),
    "chaotic_camera": (-0.6, "Ambulance"),
    "low_energy": (-0.6, "Clutch / 'لا اريد شي ميت'"),
    "indie_feeling": (-0.4, "'لا اريد شي ميت'"),
}

# Which scoring dimension a free-text/feedback trait reinforces (for weight learning).
TRAIT_TO_DIMENSION: dict[str, str] = {
    "strong_opening": "opening",
    "slow_opening": "opening",
    "strong_story": "story_quality",
    "coherence": "story_quality",
    "confusing_story": "story_quality",
    "event_quality": "story_progression",
    "event_progression": "story_progression",
    "strong_acting": "acting_cast",
    "weak_cast": "acting_cast",
    "fast_pacing": "pacing_continuity",
    "slow_pacing": "pacing_continuity",
    "continuous_events": "pacing_continuity",
    "excessive_dialogue": "pacing_continuity",
    "strong_production": "production",
    "low_production": "production",
    "chaotic_camera": "production",
    "strong_tension": "tension_action",
    "continuous_tension": "tension_action",
    "entertaining": "tension_action",
}

# Which penalty a negative trait reinforces.
TRAIT_TO_PENALTY: dict[str, str] = {
    "slow_opening": "slow_opening",
    "low_initial_engagement": "slow_opening",
    "slow_pacing": "slow_opening",
    "excessive_dialogue": "excessive_dialogue",
    "confusing_story": "confusing_story",
    "weak_cast": "weak_cast",
    "chaotic_camera": "chaotic_camera",
    "low_production": "low_production",
    "low_energy": "low_production",
    "indie_feeling": "low_production",
    "irrational_plotting": "irrational_plotting",
    "generic_high_concept": "generic_high_concept",
    "franchise_dependency": "franchise_dependency",
}
