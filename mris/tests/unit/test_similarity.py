from mris.memory.vocabulary import characteristics_to_traits
from mris.scoring.similarity import MIN_SHARED, compare


def test_genre_overlap_alone_is_not_similarity():
    town = characteristics_to_traits(["crime", "heist", "strong acting", "strong story", "realistic action"])
    generic = {"crime": 1.0, "modern_setting": 1.0}
    assert compare(generic, [("The Town", town, 0.8)], {}) == []


def test_multi_characteristic_match_counts():
    last_breath = characteristics_to_traits(
        ["realistic survival", "offshore", "rescue", "time pressure", "continuous danger", "strong tension"]
    )
    cand = {"offshore": 1.0, "rescue": 0.8, "survival": 0.8, "time_pressure": 0.8, "strong_tension": 0.8}
    matches = compare(cand, [("Last Breath", last_breath, 1.0)], {})
    assert matches and matches[0].title == "Last Breath"
    assert len(matches[0].shared) >= MIN_SHARED
