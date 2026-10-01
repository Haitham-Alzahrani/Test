from mris.research.evidence import EvidenceSummary, SourceInput, extract_signals


def _fields(text):
    return {(s.field, s.polarity) for s in extract_signals(text)}


def test_opening_positive_and_negative_phrases():
    assert ("opening", 1) in _fields("The film wastes no time and hits the ground running.")
    assert ("opening", -1) in _fields("The first act is slow and there is a lengthy setup.")
    assert ("opening", -1) in _fields("It takes a while to get going.")


def test_negation_is_clause_scoped():
    sigs = _fields("It is not a slow start at all.")
    assert ("opening", 1) in sigs and ("opening", -1) not in sigs
    # "no" inside "wastes no time" must not negate the next clause
    assert ("opening", -1) not in _fields("It wastes no time and hits the ground running.")


def test_opening_minutes_extracted():
    sigs = extract_signals("It takes 40 minutes before anything happens.")
    assert any(s.field == "opening_minutes" and float(s.phrase) == 40 for s in sigs)


def test_flags():
    flags = {s.flag for s in extract_signals("Shaky cam everywhere. Talky and a slow-burn.") if s.flag}
    assert {"chaotic_camera", "excessive_dialogue", "slow_burn"} <= flags


def test_franchise_dependency_phrases():
    assert ("franchise", -1) in _fields("You need to have seen the previous films.")
    assert ("franchise", 1) in _fields(
        "It works as a standalone and you don't need to have seen the first one."
    )


def test_summary_counts_domains_once_per_source():
    sig = extract_signals("Slow start. Slow start again. Slow opening.")
    one = EvidenceSummary.from_sources([SourceInput("u1", "a.com", "professional", 1.0, sig)])
    assert one.get("opening").neg_domains == {"a.com"}
    assert one.get("opening").neg < 2.0  # repetition on one page is not consensus
    assert one.score("opening") < 0.4
    assert one.score("story_clarity") is None  # no evidence -> unknown, never guessed
