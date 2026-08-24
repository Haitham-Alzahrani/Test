# -*- coding: utf-8 -*-
"""Apply the F-150 hard filters to the local mirror and print the report.

Kept in the repo so the result table is reproducible from the same database:

    python -m haraj.cli backfill "f150 2011" ... "f150"
    python analyze_f150.py
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys

from haraj.normalize import fold

DB = sys.argv[1] if len(sys.argv) > 1 else "haraj.db"

# ---- vocabulary ---------------------------------------------------------
CREW = ["غمارتين", "غمارتان", "crew cab", "supercrew", "دبل كابين", "غمارتيين"]
SUPER = ["غماره ونص", "غمارة ونص", "غماره و نص", "supercab", "super cab", "extended cab", "غمارهونص"]
REG = ["غماره", "غمارة", "regular cab", "single cab", "استاندر", "ستاندر", "غماره واحده"]

# Elongation-tolerant: sellers write `بدووون دبل` for emphasis, which folds to
# `بدوون دبل` and never matches a fixed string.
NO_4WD_RE = re.compile(
    r"(?:بدو+ن|غير|بلا|ما\s*ف[يى]ه|مافيه|مب|مو|ليس|من\s+غير)\s*(?:دبل|4wd|4x4)")
YES_4WD = ["دبل", "4wd", "4x4", "دفع رباعي", "فور ويل", "دبلن"]

DAMAGED = ["مصدوم", "مصدومه", "حادث", "حوادث", "تشليح", "شاصي", "مضروب", "مشلح",
           "قطع غيار", "تعرض لحادث", "بودي مصدوم"]
# `خالي من الحوادث` and `بدون حوادث` mean the opposite of `حادث`, and 47 of the
# listings in the mirror say exactly that.  Negated mentions are stripped out
# before the damage vocabulary is applied.
NOT_DAMAGED_RE = re.compile(
    r"(?:خالي[هة]?\s+من|خلو\s+من|بدون|بلا|ما\s*ف[يى]ه|مافيه|لا\s+يوجد|غير|مب|مو)"
    r"\s*(?:ال)?(?:حوادث|حادث|صدمات|مصدوم|صدام)")

# A wanted ad announces itself in its TITLE.  Matching these anywhere in the
# body flags every showroom whose boilerplate says `ابحث في حسابنا`.
WANTED = ["مطلوب", "ادور", "أدور", "ابحث", "دور على", "wanted", "من يبيع",
          "ابغى اشتري", "انا شاري", "انا شرا", "الي عنده", "اللي عنده",
          "اشتري", "ابي اشتري", "للشراء", "نشتري"]

ECOBOOST = ["ايكوبوست", "ايكو بوست", "اكوبوست", "ecoboost", "eco boost", "تيربو", "turbo", "3.5", "2.7"]
V8 = ["v8", "ثمانيه سلندر", "8 سلندر", "ثماني سلندر", "ثمانية سلندر", "5.0", "6.2", "v 8", "8 سلندرات"]
V6 = ["v6", "سته سلندر", "6 سلندر", "ست سلندر", "ستة سلندر", "3.7", "3.3", "v 6"]

RAPTOR = ["رابتر", "رابتور", "raptor", "svt"]

SOLD = ["تم البيع", "تم البيعه", "تم بيعها", "مباع", "انباع", "تم التنازل",
        "sold", "تم البيع ولله الحمد", "البيع تم", "تم بيع"]
# Parts and accessories carry the exact same `f150 2013` tags as the trucks,
# and the API's carOrRelated field does not reliably separate them, so they are
# filtered on vocabulary.
PARTS = [
    "قطع غيار", "قطع", "قماشات", "قماش", "سماعه", "سماعات", "مضخم", "شاشه",
    "جنوط", "جنط", "كفرات", "اطارات", "رفارف", "رفرف", "كشافات", "كشاف",
    "مثبت سرعة", "مثبت سرعه", "تركيب و تفعيل", "دعميات", "دعامية", "شمعه",
    "شمعات", "بواجي", "فلتر", "كتباك", "كت باك", "كاتباك", "شكمان", "ماسورة",
    "كبوت", "صدام", "شبك", "مرايا", "مراية", "دركسون", "يايات", "مقص",
    "دفريشن", "دركسيون", "علبة دركسيون", "صندوق", "حوض", "قير علاق", "مكينة", "مكينه", "قزاز", "زجاج",
    "فرش", "جلد", "ديكور", "ستيكر", "استيكر", "رول بار", "درج جانبي",
    "ردياتير", "كمبروسر", "طرمبة", "بطارية", "بطاريه", "تيل", "دسك",
    "عفشة", "كويلات", "ونش", "غطاء", "تغطية", "بلاطة", "شد فورد", "شد ",
    "دودة", "قاعدة", "بكس حديد", "خزان", "طقم", "اكسسوار", "ملحقات",
    "كت ", "بديت", "بدي كت", "ليدات", "ليد", "سبويلر", "قواعد", "بومبر",
    "وحدة تحكم", "وحده تحكم", "عداد فل", "بيماس", "انتيك", "ايس كريم",
    "ايسكريم", "هوك", "كسوارت", "اسطب", "اصطب", "هوايات", "وطايه", "واجهه",
    "وجهيه", "مفتاح", "اديتر", "حماية", "تربوئ", "دبه ", "دبة ", "اشعار",
    "تحويل سينك", "يد إشارة", "يد اشارة", "بوشواكر", "bushwacker", "flares",
]

NO_PRICE_WORDS = ["على السوم", "ع السوم", "السوم", "بدل", "للبدل", "قابل للتفاوض",
                  "قابل للنقاش", "تفاوض", "مبادله", "بدون سعر"]


def has(text: str, needles) -> bool:
    return any(fold(n) in text for n in needles)


def classify_cab(text: str) -> str:
    # Order matters: `غماره ونص` and `غمارتين` both contain `غماره`.
    if has(text, CREW):
        return "crew"
    if has(text, SUPER):
        return "supercab"
    if has(text, REG):
        return "regular"
    return "unknown"


def classify_4wd(text: str, field) -> tuple[str, str]:
    """(value, provenance).  Absence is never evidence of 2WD."""
    if NO_4WD_RE.search(text):
        return "no", "text"
    if has(text, YES_4WD):
        return "yes", "text"
    if field == 1:
        return "yes", "field"
    if field == 0:
        return "no", "field"
    return "unknown", "-"


def classify_engine(text: str) -> str:
    if has(text, ECOBOOST):
        return "ecoboost-v6"
    if has(text, V8):
        return "v8"
    if has(text, V6):
        return "v6"
    return "unknown"


def transmission_ok(year: int | None, engine: str) -> tuple[bool, str]:
    """6R80 availability by year."""
    if year is None:
        return False, "no year"
    if 2011 <= year <= 2016:
        return True, "6R80 (all engines)"
    if year == 2017:
        if engine == "ecoboost-v6":
            return False, "2017 EcoBoost = 10R80"
        if engine in ("v8", "v6"):
            return True, "6R80 (3.3 V6 / 5.0 V8)"
        return False, "2017, engine unknown -> 6R80 unproven"
    if year in (2009, 2010):
        return False, "2009-10: only 5.4 V8 got 6R80"
    return False, f"{year} outside 6R80 range"


def main() -> None:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    # Haraj's own tags miss listings its classifier never typed, so the corpus
    # is swept by tag *and* by free-text search; match on either here.
    rows = db.execute(
        "SELECT * FROM posts WHERE status='live' "
        "AND tags NOT LIKE '%قطع غيار%' "
        "AND (tags LIKE '%f150%' OR norm LIKE '%f150%' "
        "     OR norm LIKE '%اف 150%' OR norm LIKE '%f 150%' "
        "     OR norm LIKE '%اف150%')"
    ).fetchall()

    matches, near, unknown, rejected = [], [], [], 0
    for r in rows:
        text = " ".join(filter(None, [r["norm"] or "", fold(r["title"]), fold(r["body"]),
                                      fold(" ".join(json.loads(r["tags"] or "[]")))]))
        year = r["year"]
        title_years = [int(y) for y in re.findall(r"\b(20[01]\d)\b", fold(r["title"] or ""))]
        if year is None and title_years:
            year = max(title_years)

        tags_f = fold(" ".join(json.loads(r["tags"] or "[]")))
        if "f250" in tags_f and "f150" not in tags_f:
            rejected += 1        # a different truck
            continue
        if has(fold(r["title"]), WANTED):
            rejected += 1        # wanted ad, not a car for sale
            continue
        if has(fold(r["title"]), SOLD) or has(text, SOLD):
            rejected += 1        # already sold
            continue
        if has(fold(r["title"]), PARTS):
            rejected += 1        # a part, not a truck
            continue
        if has(NOT_DAMAGED_RE.sub(" ", text), DAMAGED):
            rejected += 1        # damaged / salvage
            continue
        if has(text, RAPTOR):
            rejected += 1        # Raptor was never sold as a regular cab
            continue

        # A listing with no car field filled in at all and a parts-shaped title
        # is an accessory ad riding the same tag.
        car_fields = [r["mileage"], r["price"], r["is_4wd"], r["gear"] or None,
                      r["fuel"] or None]
        if not any(v is not None for v in car_fields) and r["kind"] != "CAR":
            rejected += 1
            continue

        cab = classify_cab(text)
        fourwd, prov = classify_4wd(text, r["is_4wd"])
        engine = classify_engine(text)
        km = r["mileage"]
        # Sellers leave the odometer field at its default; on a 2009-2017 truck
        # anything under 5,000 km is a data-entry artefact, not a reading.
        if km is not None and km < 5_000:
            km = None
        price = r["price"]
        # Likewise a "price" of a few riyals or of over two million is noise.
        if price is not None and not (1_000 <= price <= 2_000_000):
            price = None
        # `على السوم` / `بدل` / blank all count as no price and PASS.  But a
        # number attached to the sum -- `السوم السوم (((( 100 ))))` -- is a
        # stated floor of 100,000 SAR, not a blank.
        no_price = price is None

        fails = []
        tx_ok, tx_note = transmission_ok(year, engine)
        if not tx_ok:
            fails.append(f"transmission: {tx_note}")
        if cab == "crew":
            fails.append("cab: crew (غمارتين)")
        elif cab == "supercab":
            fails.append("cab: supercab (غمارة ونص)")
        if fourwd == "no":
            fails.append("4wd: no")
        if km is not None and km >= 200_000:
            fails.append(f"mileage: {km:,} km")
        if price is not None and price >= 50_000:
            fails.append(f"price: {price:,} SAR")

        unknowns = []
        if cab == "unknown":
            unknowns.append("cab")
        if fourwd == "unknown":
            unknowns.append("4wd")
        if km is None:
            unknowns.append("km")

        rec = dict(id=r["id"], year=year, cab=cab, fourwd=fourwd, prov=prov,
                   engine=engine, km=km, price=price, no_price=no_price,
                   city=r["city"], seller=r["author"], url=r["url"],
                   title=r["title"], fails=fails, unknowns=unknowns,
                   posted=r["posted_date"])

        if fails:
            if len(fails) == 1:
                near.append(rec)
            continue
        if unknowns:
            # Only worth a phone call if the listing is substantive enough to
            # be a truck at all: a known odometer inside the target range, or a
            # confirmed cab type.  Everything else is an accessory ad or a
            # three-word listing with nothing in it.
            if km is not None or cab == "regular":
                unknown.append(rec)
            else:
                rejected += 1
        else:
            matches.append(rec)

    out = dict(matches=matches, near=near, unknown=unknown,
               scanned=len(rows), rejected=rejected)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
