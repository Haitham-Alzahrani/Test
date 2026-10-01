"""End-to-end: systematic search, exclusions, persistent cursor and 'continue' semantics."""

from mris.models import ResearchStatus


def statuses(svc):
    return {i.candidate: i.research_status for i in svc.repos.queue.list(None, 1000)}


def test_continue_finds_first_strong_candidate_and_resumes(svc):
    result, rec, text = svc.continue_search()
    # January 2026: sci-fi rejected, Mutiny already watched (blocked), slow opening rejected, Korean rejected
    st = statuses(svc)
    assert st["Star Rift (2026)"] == ResearchStatus.REJECTED
    assert st["Mutiny (2026)"] == ResearchStatus.BLOCKED
    assert st["Quiet Harbor (2026)"] == ResearchStatus.REJECTED
    assert st["Seoul Night (2026)"] == ResearchStatus.REJECTED
    # It did not stop in January to ask; it went on to February and found Iron Tide
    assert rec is not None and rec.candidate.movie.title == "Iron Tide"
    assert "Iron Tide (2026)" in text
    assert "Quiet Harbor" not in text and "Star Rift" not in text  # rejected titles are never shown
    assert result.months_scanned == ["January 2026", "February 2026"]
    cursor = svc.engine().cursor()
    assert (cursor.year, cursor.month) == (2026, 2)
    assert cursor.last_candidate == "Iron Tide (2026)"

    # history is stored; a second continue resumes AFTER Iron Tide, never restarts at January
    assert svc.repos.recommendations.latest(svc.user).movie.title == "Iron Tide"
    calls_before = list(svc.providers.metadata.detail_calls)
    result2, rec2, text2 = svc.continue_search()
    new_calls = svc.providers.metadata.detail_calls[len(calls_before) :]
    assert 101 not in new_calls and 103 not in new_calls  # January is not re-researched
    st = statuses(svc)
    assert (
        st["Last Run (2026)"] == ResearchStatus.INSUFFICIENT_EVIDENCE
    )  # one thin source -> keep researching
    assert st["Wick Legacy (2026)"] == ResearchStatus.REJECTED  # franchise dependency
    assert rec2 is None
    # range 2026 -> 2025 with nothing else: continues through every month then reports exhaustion
    assert result2.exhausted


def test_rejections_are_stored_with_reasons(svc):
    svc.continue_search()
    rejected = {r.title: r for r in svc.repos.rejected.list(svc.user, "research_pipeline")}
    assert "science fiction" in rejected["Star Rift"].rejection_reason.lower()
    assert (
        "slow" in rejected["Quiet Harbor"].rejection_reason.lower()
        or "burn" in rejected["Quiet Harbor"].rejection_reason.lower()
    )
    assert "korean" in rejected["Seoul Night"].rejection_reason.lower()


def test_recommended_movie_is_not_repeated_and_feedback_closes_loop(svc):
    _, rec, _ = svc.continue_search()
    assert rec.candidate.movie.title == "Iron Tide"
    assert svc.recommend(1, research=False) == []  # never shown twice
    reply = svc.handle_message("شاهدته وأعجبني جدًا")
    assert reply.data["intent"] == "feedback" and reply.data["rating"] == "loved"
    hist = svc.repos.recommendations.latest(svc.user)
    assert hist.user_response == "watched"


def test_cast_rejection_of_last_recommendation(svc):
    svc.continue_search()
    reply = svc.handle_message("لا يعجبني الممثلين")
    assert reply.data["intent"] == "cast_reject"
    movie = svc.repos.movies.find("Iron Tide", 2026)
    assert svc.repos.rejected.get(svc.user, movie).source_of_rejection == "user_cast"
    prefs = svc.repos.actors.for_actor(svc.user, "Lead Star")
    assert prefs and prefs[0].scope == "movie"  # not a universal actor ban


def test_per_run_limit_keeps_cursor(svc):
    result, rec, text = svc.continue_search(max_candidates=2)
    assert rec is None and result.evaluated == 2
    assert "per-run limit" in result.stopped_reason
    cursor = svc.engine().cursor()
    assert cursor.last_candidate == "Mutiny (2026)"
    _, rec, _ = svc.continue_search()
    assert rec.candidate.movie.title == "Iron Tide"


def test_without_web_provider_nothing_is_recommended(session, settings):
    from mris.service import MRIS
    from tests.conftest import TODAY
    from tests.fixtures.fake_providers import fake_providers

    svc = MRIS(session, providers=fake_providers(web=False), settings=settings, today=TODAY)
    svc.init()
    result, rec, _ = svc.continue_search()
    assert rec is None  # metadata alone never justifies a recommendation
    iron = svc.repos.candidates.for_movie(svc.repos.movies.find("Iron Tide", 2026))
    assert iron.research_status == ResearchStatus.INSUFFICIENT_EVIDENCE
    # manual evidence (e.g. pasted by the user or an agent with web access) completes the picture
    from tests.fixtures.fake_providers import REVIEWS

    for url, txt in REVIEWS["Iron Tide"]:
        cand = svc.add_evidence("Iron Tide", 2026, url, txt)
    assert cand.research_status == ResearchStatus.PASSED
    assert svc.recommend(1, research=False)[0].candidate.movie.title == "Iron Tide"


def test_explicit_title_research_and_explain(svc):
    cand = svc.research_title("Iron Tide", 2026)
    assert cand.research_status == ResearchStatus.PASSED
    text = svc.explain("Iron Tide", 2026)
    assert "opening" in text and "Iron Tide" in text


def test_references_enriched_from_verified_metadata(svc):
    svc.continue_search()
    nobody = svc.repos.movies.find("Nobody", 2021)
    traits = svc.repos.movies.traits(nobody.id)
    assert nobody.metadata_verified and nobody.tmdb_id == 900
    assert {"revenge", "crime", "heist", "modern_setting"} <= set(traits)
    assert svc.user.profile["references_enriched"] is True
