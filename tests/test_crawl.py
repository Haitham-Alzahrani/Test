# -*- coding: utf-8 -*-
"""Parsing tests.  No network: everything runs off saved fixtures."""

import json
import pathlib

import pytest

from haraj.crawl import _4wd_from, parse_listing, post_from_graphql

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def c300_page():
    return (FIXTURES / "listing_c300.html").read_text(encoding="utf-8")


class TestHtmlListing:
    def test_meta_and_href_fields(self, c300_page):
        p = parse_listing(c300_page, 11187085515)
        assert p.title == "كرايسلر C300 موديل 2017"     # ` | موقع حراج` stripped
        assert p.city == "الدمام"                        # from /city/X
        assert p.author == "abu_fatema2026"              # from /users/X
        assert "حراج السيارات" in p.tags                 # from /tags/X
        assert "C300 2017" in p.tags

    def test_post_date_comes_from_the_image_path(self, c300_page):
        # https://<...>cdn.haraj.com.sa/userfiles30/2026-08-24/...
        p = parse_listing(c300_page, 11187085515)
        assert p.posted_date == "2026-08-24"
        assert p.images and all("haraj.com.sa" in i for i in p.images)

    def test_body_merges_attribute_block_with_seller_prose(self, c300_page):
        p = parse_listing(c300_page, 11187085515)
        assert "الممشى: 260 ألف كيلو" in p.body     # structured block
        assert "نص فل" in p.body                    # seller's prose
        assert "قير اوتماتيك" in p.body

    def test_mileage_from_block_is_thousands(self, c300_page):
        p = parse_listing(c300_page, 11187085515)
        assert p.mileage == 260_000                 # not 260

    def test_price_scored_out_of_a_decoy_rich_body(self, c300_page):
        # Body contains `موديل 2017`, `6.1`, `6.4` and `260k` alongside
        # `الحد 52000 آلاف`.
        p = parse_listing(c300_page, 11187085515)
        assert p.price == 52_000


class TestGraphqlMapping:
    def item(self, **kw):
        base = {
            "id": 187053029,
            "URL": "11187053029/فورد_F150/",
            "title": "فورد F150 2013 دبل",
            "bodyTEXT": "نظيف",
            "postDate": 1787495130,
            "authorUsername": "someone",
            "city": "الرياض",
            "tags": ["حراج السيارات", "فورد", "f150", "f150 2013"],
            "imagesList": [],
            "price": None,
            "carInfo": {"is4DW": True, "model": 2013, "mileage": 300,
                        "fuel": "GASOLINE", "gear": "AUTO", "condition": "USED"},
        }
        base.update(kw)
        return base

    def test_full_id_recovered_from_url(self):
        # The API strips the site-wide prefix from ids; the URL keeps it.
        assert post_from_graphql(self.item()).id == 11187053029

    def test_mileage_field_is_thousands(self):
        """⚠ carInfo.mileage == 300 means 300,000 km, not 300 km."""
        p = post_from_graphql(self.item())
        assert p.mileage == 300_000

    def test_mileage_falls_back_to_the_body(self):
        item = self.item(bodyTEXT="العداد : 332،000 كيلو")
        item["carInfo"]["mileage"] = None
        assert post_from_graphql(item).mileage == 332_000

    def test_placeholder_price_of_one_is_no_price(self):
        item = self.item(price={"formattedPrice": "1", "inputPrice": "1"})
        assert post_from_graphql(item).price is None

    def test_real_price_kept(self):
        item = self.item(price={"formattedPrice": "38,000", "inputPrice": "38000"})
        assert post_from_graphql(item).price == 38_000

    def test_posted_date(self):
        assert post_from_graphql(self.item()).posted_date == "2026-08-23"


class Test4WD:
    """⚠ The 4WD line only appears when the seller filled that field in."""

    def test_absent_means_unknown_not_2wd(self):
        assert _4wd_from("XL 2014 Used\nAutomatic\nGasoline\nmileage: 130 KM") is None
        assert _4wd_from("فورد F150 2013 غمارة") is None

    def test_present_means_4wd(self):
        assert _4wd_from("XL 2014 Used\nAutomatic\n4WD") == 1
        assert _4wd_from("فورد F150 دبل") == 1

    @pytest.mark.parametrize("phrase", [
        "بدون دبل", "غير دبل", "ما فيه دبل", "مب دبل",
    ])
    def test_negations_mean_2wd(self, phrase):
        assert _4wd_from(f"فورد F150 {phrase}") == 0

    def test_graphql_null_is_unknown(self):
        item = {
            "id": 1, "URL": "111/x/", "title": "t", "bodyTEXT": "",
            "postDate": 0, "authorUsername": "", "city": "", "tags": [],
            "imagesList": [], "price": None,
            "carInfo": {"is4DW": None, "model": 2013, "mileage": None},
        }
        assert post_from_graphql(item).is_4wd is None


class TestElongatedNegation:
    """Sellers stretch the negation for emphasis: `الموتر بدووون دبل`."""

    @pytest.mark.parametrize("text", [
        "الموتر بدووون دبل",
        "الموتر بدوووووون دبل",
        "السيارة من غير دبل",
        "مافيه دبل",
        "بلا دبل",
    ])
    def test_elongated_and_varied_negations_are_2wd(self, text):
        assert _4wd_from(text) == 0

    def test_positive_still_reads_as_4wd(self):
        assert _4wd_from("الموتر دبل دفلوك") == 1
