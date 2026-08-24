# -*- coding: utf-8 -*-
import pytest

from haraj.normalize import (
    canonical_terms, expand, fold, parse_block_mileage, parse_mileage,
    parse_price, tokens,
)


class TestFolding:
    @pytest.mark.parametrize("a,b", [
        ("مصدومة", "مصدومه"),          # ta marbuta
        ("الطائف", "الطايف"),          # ya family
        ("أحمد", "احمد"),              # alef family
        ("إبراهيم", "ابراهيم"),
        ("آل", "ال"),
        ("مسؤول", "مسوول"),            # waw family
        ("كامري", "كامرى"),
    ])
    def test_pairs_fold_together(self, a, b):
        assert fold(a) == fold(b)

    def test_persian_urdu_lookalikes(self):
        # A live Haraj title, typed on a non-Arabic keyboard.
        assert fold("صيانہ آتو ميتک غسالات") == "صيانه اتو ميتك غسالات"
        assert fold("ٹويوٹا") == fold("تويوتا")
        assert fold("پورد") == fold("بورد")

    def test_arabic_indic_digits(self):
        assert fold("٢٠١٢") == "2012"
        assert fold("۱۹۹۹") == "1999"
        assert fold("موديل ٢٠١٣") == "موديل 2013"

    def test_diacritics_tatweel_zerowidth(self):
        assert fold("مُحَمَّد") == "محمد"
        assert fold("سـيـارة") == "سياره"
        assert fold("سيار​ة") == "سياره"

    def test_hamza_dropped(self):
        assert fold("ماء") == "ما"

    def test_nfkc_and_case(self):
        assert fold("Ｆ１５０") == "f150"
        assert fold("FORD F150") == "ford f150"


class TestRunCollapsing:
    def test_three_or_more_collapse_to_two(self):
        assert fold("كثييييير") == "كثيير"
        assert fold("حلوووووو") == "حلوو"

    def test_doubles_are_preserved(self):
        # الممملكة -> الملكة is a real collision, so doubles stay put.
        assert fold("المملكة") == "المملكه"
        assert fold("الممملكة") == "المملكه"   # 3 mims -> 2, not 1
        assert fold("المملكة") != fold("الملكة")

    def test_digit_runs_never_collapse(self):
        assert fold("15000") == "15000"
        assert fold("1111") == "1111"
        assert fold("ماشي 300000") == "ماشي 300000"


class TestDigitSeparators:
    def test_thousands_commas_stripped(self):
        assert fold("15,000") == "15000"
        assert fold("332،000") == "332000"      # Arabic comma

    def test_decimal_point_preserved(self):
        assert fold("1.5 مليون") == "1.5 مليون"

    def test_sentence_dots_removed(self):
        assert fold("نظيف. جدا") == "نظيف جدا"


class TestSynonyms:
    def test_bidirectional(self):
        # The seller's title and Haraj's own tag on the same live listing.
        assert fold("اكسبيدشن") in expand("اكسبديشن")
        assert fold("اكسبديشن") in expand("اكسبيدشن")

    def test_transliterations(self):
        assert "camry" in expand("كامري")
        assert fold("كامري") in expand("camry")

    def test_multiword_entries(self):
        assert fold("لاندكروزر") in expand("لاند كروزر")
        assert fold("لاند كروزر") in expand("landcruiser")

    def test_cab_and_drivetrain_terms_stay_distinct(self):
        # غماره (regular) must never expand into غمارتين (crew) -- the whole
        # F-150 search turns on that distinction.
        assert fold("غمارتين") not in expand("غماره").split()
        assert fold("غماره ونص") not in expand("غماره")

    def test_city_aliases(self):
        assert fold("جدة") in expand("jeddah")
        assert fold("الطايف") in expand("الطائف")

    def test_canonical_terms(self):
        assert "دبل" in canonical_terms("فورد f150 دبل غماره")
        assert "غماره" in canonical_terms("فورد f150 دبل غماره")


class TestAmountParsing:
    DECOYS = "موديل 2012 جوال 0501234567 ماشي 475الف بسعر 45 ألف"

    def test_price_beats_decoys(self):
        assert parse_price(self.DECOYS) == 45_000

    def test_mileage_beats_decoys(self):
        assert parse_mileage(self.DECOYS) == 475_000

    def test_bare_year_is_not_a_price(self):
        assert parse_price("موديل 2013") is None
        assert parse_price("للبيع فورد 2015") is None

    def test_year_with_currency_marker_is_a_price(self):
        assert parse_price("السعر 2000 ريال") == 2_000

    def test_phone_numbers_are_not_amounts(self):
        assert parse_price("للتواصل 0501234567") is None
        # Spaced phone numbers are the common form on Haraj.
        assert parse_price("واتس 053 082 8812") is None

    def test_multipliers(self):
        assert parse_price("بسعر 45 ألف") == 45_000
        assert parse_price("بسعر 1.5 مليون") == 1_500_000

    def test_multiplier_word_after_a_full_number_is_emphasis(self):
        # `الحد 52000 آلاف` is 52,000 SAR, not 52 million.
        assert parse_price("الحد 52000 آلاف") == 52_000

    def test_no_price_listed(self):
        assert parse_price("على السوم") is None
        assert parse_price("للبدل فقط") is None

    def test_nearest_marker_wins(self):
        # `اف 150` sits three tokens from العداد; the real mileage is one away.
        body = "فورد غماره 8 سلندر دبل اف 150 الموديل 2013 العداد : 332،000 كيلو"
        assert parse_mileage(body) == 332_000

    def test_bare_hundreds_after_mileage_marker_are_thousands(self):
        assert parse_mileage("الممشى 300") == 300_000
        assert parse_mileage("ماشي 175") == 175_000


class TestStructuredBlockMileage:
    """⚠ The site's mileage field is expressed in THOUSANDS."""

    def test_english_mirror_block(self):
        # `mileage: 130 KM` on a real listing means 130,000 km.
        assert parse_block_mileage("XL 2014 Used\nAutomatic\nGasoline\n"
                                   "mileage: 130 KM\n4WD") == 130_000

    def test_arabic_block(self):
        assert parse_block_mileage("الممشى: 260 ألف كيلو") == 260_000

    def test_not_taken_literally(self):
        # The failure this guards against: a 130,000 km truck reading as 130 km
        # and looking nearly new.
        assert parse_block_mileage("mileage: 130 KM") != 130

    def test_absent_block(self):
        assert parse_block_mileage("سيارة نظيفة") is None


class TestSoumPricing:
    """`السوم` (open to offers) is a price marker when a number follows it."""

    def test_soum_with_bare_hundreds_is_thousands(self):
        # Live listing: `السوم السوم (((( 100 ))))` -- 100,000 SAR.
        assert parse_price("السوم السوم 100") == 100_000

    def test_soum_with_full_number(self):
        assert parse_price("السوم وصل 36500") == 36_500

    def test_soum_alone_is_still_no_price(self):
        assert parse_price("البيع على السوم") is None


class TestModelNumbersAreNotAmounts:
    def test_glued_model_number(self):
        assert parse_price("للبيع f150 موديل 2013") is None
        assert parse_price("فورد f250 للبيع") is None

    def test_split_model_number(self):
        # `F-150` folds to `f 150`, leaving a bare 150 next to `للبيع`.
        assert parse_price("للبيع فورد اف 150 دبل") is None
        assert parse_price("للبيع فورد F-150") is None

    def test_a_real_price_beside_a_model_number_still_parses(self):
        assert parse_price("للبيع فورد اف 150 السوم 45 الف") == 45_000
