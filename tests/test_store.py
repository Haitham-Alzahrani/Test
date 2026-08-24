# -*- coding: utf-8 -*-
import pytest

from haraj.store import Post, Store


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    yield s
    s.close()


def truck(pid, title, **kw):
    kw.setdefault("author", f"seller{pid}")
    kw.setdefault("year", 2013)
    return Post(id=pid, title=title, **kw)


class TestPhraseExclusion:
    """⚠ Exclusions are comma-separated PHRASES, never whitespace-split words.

    Arabic negation is a prefix, so `بدون دبل` ("no 4WD") *contains* `دبل`
    ("4WD").  Splitting the exclusion on whitespace produces `NOT LIKE %دبل%`,
    which drops every 4WD truck on the site -- zero results, no error, the
    exact opposite of what was asked for.
    """

    @pytest.fixture()
    def populated(self, store):
        store.upsert(truck(1, "فورد F150 2013 دبل غمارة", is_4wd=1))
        store.upsert(truck(2, "فورد F150 2013 غمارة بدون دبل", is_4wd=0))
        store.upsert(truck(3, "فورد F150 2013 غمارتين دبل", is_4wd=1))
        store.upsert(truck(4, "مطلوب فورد F150 2013 دبل", is_4wd=1))
        return store

    def test_phrase_exclusion_keeps_4wd_and_drops_negations(self, populated):
        ids = [r["id"] for r in populated.search(
            "f150", exclude="بدون دبل, غمارتين, مطلوب")]
        assert 1 in ids                      # 4WD regular cab survives
        assert 2 not in ids                  # "بدون دبل" dropped
        assert 3 not in ids                  # crew cab dropped
        assert 4 not in ids                  # wanted-ad dropped

    def test_whitespace_splitting_would_return_nothing(self, populated):
        # Demonstrates the bug being avoided: excluding the words separately
        # takes every 4WD listing with it.
        naive = populated.search("f150", exclude="بدون,دبل")
        assert [r["id"] for r in naive] == [2] or [r["id"] for r in naive] == []
        assert 1 not in [r["id"] for r in naive]

    def test_empty_exclusion_is_a_no_op(self, populated):
        assert len(populated.search("f150", exclude="")) == 4
        assert len(populated.search("f150", exclude="  ,  ")) == 4


class TestSearch:
    def test_synonym_hit(self, store):
        store.upsert(truck(1, "فورد F150 دبل"))
        # `4wd` never appears in the listing; it reaches it through norm_expanded.
        assert [r["id"] for r in store.search("4wd")] == [1]

    def test_exact_spelling_outranks_synonym(self, store):
        store.upsert(truck(1, "فورد اكسبديشن 2013"))
        store.upsert(truck(2, "فورد اكسبيدشن 2013"))
        rows = store.search("اكسبديشن")
        assert [r["id"] for r in rows] == [1, 2]

    def test_no_price_passes_max_price(self, store):
        store.upsert(truck(1, "فورد F150 على السوم", price=None))
        store.upsert(truck(2, "فورد F150", price=80_000))
        ids = [r["id"] for r in store.search("f150", max_price=50_000)]
        assert ids == [1]

    def test_mileage_and_year_filters(self, store):
        store.upsert(truck(1, "فورد F150", year=2013, mileage=180_000))
        store.upsert(truck(2, "فورد F150", year=2013, mileage=310_000))
        store.upsert(truck(3, "فورد F150", year=2019, mileage=90_000))
        ids = {r["id"] for r in store.search("f150", max_km=200_000, max_year=2017)}
        assert ids == {1}

    def test_dupe_collapsing(self, store):
        # Same showroom, same truck, relisted the next morning.
        store.upsert(Post(id=10, title="فورد F150 2013 دبل", author="معرض العمر", price=45_000))
        store.upsert(Post(id=11, title="دبل F150 فورد 2013", author="معرض العمر", price=45_000))
        rows = store.search("f150")
        assert len(rows) == 1


class TestTombstones:
    def test_gap_is_recorded_and_hidden(self, store):
        store.upsert(truck(1, "فورد F150 دبل"))
        store.tombstone(2)
        assert 2 in store.known_ids()
        assert [r["id"] for r in store.search("f150")] == [1]


class TestSavedSearches:
    def test_watch_check_only_returns_new_posts(self, store):
        store.upsert(truck(1, "فورد F150 دبل غمارة"))
        store.watch_add("f150", q="f150 غمارة دبل", exclude="بدون دبل, غمارتين")

        first = store.watch_check("f150")
        assert [r["id"] for r in first] == [1]

        # Nothing has been posted since -- a second check must be silent.
        assert store.watch_check("f150") == []

        store.upsert(truck(2, "فورد F150 دبل غمارة نظيفة"))
        assert [r["id"] for r in store.watch_check("f150")] == [2]
        assert store.watch_check("f150") == []

    def test_watermark_advances_past_non_matching_posts(self, store):
        store.watch_add("f150", q="f150 دبل")
        store.upsert(truck(5, "كامري 2013"))          # not a match
        assert store.watch_check("f150") == []
        store.upsert(truck(4, "فورد F150 دبل"))       # older id than 5
        # Already behind the watermark, so it is not reported as new.
        assert store.watch_check("f150") == []
