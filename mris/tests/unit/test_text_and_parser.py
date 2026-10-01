from mris.memory.parser import parse_message
from mris.text import normalize_text, normalize_title


def test_normalize_title_variants():
    assert normalize_title("Carry-On") == normalize_title("carry on")
    assert normalize_title("The Town") == "the town"
    assert normalize_text("أعجبني جدًا") == "اعجبني جدا"


def test_spec_example_mutiny_loved():
    p = parse_message("Mutiny عجبني لأن التمثيل والقصه والاحداث والتسلسل ممتازه")
    assert p.intent == "feedback"
    assert p.title == "Mutiny"
    assert p.rating_label == "loved"
    assert {"strong_acting", "strong_story", "event_quality", "event_progression", "coherence"} <= set(
        p.positive_traits
    )


def test_spec_example_amateur_disliked():
    p = parse_message("The Amateur بطيء جدًا ومللت منه من أول عشر دقائق")
    assert p.rating_label == "disliked"
    assert p.title == "The Amateur"
    assert {"slow_opening", "low_initial_engagement", "slow_pacing"} <= set(p.negative_traits)


def test_spec_example_nothing_dead():
    p = parse_message("لا اريد شي ميت")
    assert p.intent == "preference"
    assert set(p.negative_traits) >= {"low_energy", "low_production", "weak_cast", "indie_feeling"}


def test_continue_variants():
    for word in ("continue", "اكمل", "استمر"):
        assert parse_message(word).intent == "continue"


def test_watch_later_and_cast_and_last_reference():
    assert parse_message("ضعه للمشاهدة لاحقًا").intent == "watch_later"
    cast = parse_message("لا يعجبني الممثلين")
    assert cast.intent == "cast_reject" and cast.refers_to_last and not cast.universal_actor
    p = parse_message("شاهدته وأعجبني جدًا")
    assert p.rating_label == "loved" and p.refers_to_last
    assert parse_message("كان متوسط").rating_label == "medium"
    assert parse_message("ما عجبني").rating_label == "disliked"


def test_numeric_rating_and_mixed_feedback():
    p = parse_message("The Lost Bus حلو 7 من 10")
    assert p.rating_value == 7 and p.rating_label == "good"
    p = parse_message("The Night Manager عجبني بس فيه حوار كثير")
    assert p.rating_label == "liked" and "excessive_dialogue" in p.negative_traits


def test_known_title_detection():
    known = [("the town", object()), ("plane", object())]
    p = parse_message("the town رهيب", known)
    assert p.title == "the town" and p.rating_label == "loved"
