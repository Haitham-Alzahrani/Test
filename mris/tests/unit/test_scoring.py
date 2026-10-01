from datetime import date

from mris.models import Confidence, ResearchStatus
from mris.research.evidence import EvidenceSummary, SourceInput, extract_signals
from mris.scoring.assessment import assess
from mris.scoring.compatibility import compute_score, decide
from mris.scoring.defaults import DEFAULT_EXCLUSIONS
from mris.scoring.exclusions import find_exclusions
from mris.search.base import CastMember, MovieMetadata

ALL = set(DEFAULT_EXCLUSIONS)


def meta(**kw):
    base = dict(
        title="X",
        year=2026,
        tmdb_id=1,
        release_date=date(2026, 1, 1),
        original_language="en",
        countries=["US"],
        genres=["Action", "Thriller"],
        runtime=100,
        director="D",
        cast=[CastMember("A", 0, 30.0), CastMember("B", 1, 20.0)],
        budget=60_000_000,
    )
    base.update(kw)
    return MovieMetadata(**base)


def summary(*texts):
    domains = ["variety.com", "reddit.com", "theguardian.com", "imdb.com"]
    types = ["professional", "audience", "professional", "audience"]
    return EvidenceSummary.from_sources(
        [
            SourceInput(f"https://{d}/x", d, t, 0.9, extract_signals(txt))
            for txt, d, t in zip(texts, domains[: len(texts)], types[: len(texts)], strict=True)
        ]
    )


STRONG = (
    "Wastes no time; a tense, fast-paced thriller with strong performances and a clear story. Well-plotted.",
    "Hooks you immediately, relentless, edge-of-your-seat. Constant tension. Excellent action set pieces.",
    "Gripping from the start. Great acting, slick production values are high, believable characters.",
)


def test_strong_candidate_passes_with_high_confidence():
    a = assess(meta(), summary(*STRONG))
    assert a.get("opening_score") > 0.75 and a.opening_confidence == "HIGH"
    score = compute_score(a, None, metadata_verified=True)
    assert score.confidence == Confidence.HIGH
    status, _ = decide(score, [], 75, 55)
    assert status == ResearchStatus.PASSED, score.breakdown()


def test_no_evidence_means_low_confidence_not_a_guess():
    a = assess(meta(), EvidenceSummary())
    assert a.get("opening_score") is None and a.opening_confidence is None
    score = compute_score(a, None, metadata_verified=True)
    assert score.confidence == Confidence.LOW
    status, _ = decide(score, [], 75, 55)
    assert status == ResearchStatus.INSUFFICIENT_EVIDENCE


def test_slow_opening_is_rejected():
    a = assess(
        meta(),
        summary(
            "A slow start with a lengthy setup.",
            "The first act is slow and drags early.",
            "It takes 40 minutes before anything happens.",
        ),
    )
    assert a.flags.get("slow_opening") == "strong"
    keys = {e.key for e in find_exclusions(meta(), a, ALL)}
    assert "weak_opening" in keys


def test_metadata_exclusions():
    keys = lambda **kw: {e.key for e in find_exclusions(meta(**kw), None, ALL)}  # noqa: E731
    assert "science_fiction" in keys(genres=["Science Fiction"])
    assert "excluded_language" in keys(original_language="ko")
    assert "excluded_language" in keys(original_language="es")
    assert "supernatural" in keys(overview="A family moves into a haunted house.")
    assert "pre_2000_setting" in keys(overview="In 1985, a detective chases a killer.")
    assert "military_war" in keys(overview="A platoon is trapped behind enemy lines.")
    # an ex-soldier protagonist in a civilian story is fine
    assert keys(overview="A former Marine must rescue his kidnapped daughter from a cartel.") == set()
    # a modern true-story disaster tagged History is not a "historical setting"
    assert "historical_setting" not in keys(genres=["Action", "History"], overview="An oil rig explodes.")


def test_disabled_exclusion_is_not_applied():
    assert find_exclusions(meta(genres=["Science Fiction"]), None, ALL - {"science_fiction"}) == []


def test_sequel_without_standalone_evidence_is_franchise_dependent():
    a = assess(meta(collection_name="Saga Collection", collection_position=3), summary(*STRONG))
    assert a.franchise_dependency == "strong"
    assert "franchise_required" in {e.key for e in find_exclusions(meta(), a, ALL)}


def test_penalties_reduce_score():
    good = compute_score(assess(meta(), summary(*STRONG)), None, True)
    talky = compute_score(
        assess(meta(), summary(*STRONG[:2], "Talky, too much talking, dialogue-heavy.")), None, True
    )
    assert talky.total < good.total
    assert "excessive_dialogue" in talky.penalties
