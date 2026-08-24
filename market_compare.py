# -*- coding: utf-8 -*-
"""Place one listing against the rest of the local mirror.

    python market_compare.py 11186935011

Prints where the target sits on mileage and price relative to comparable
F-150s, plus the listings that actually compete with it.
"""

from __future__ import annotations

import json
import re
import sqlite3
import statistics as st
import sys

from haraj.normalize import fold

DB = "haraj.db"
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 11186935011

SOLD = ["تم البيع", "مباع", "انباع", "تم بيع", "تم التنازل"]
# Halo trims (Raptor, SVT, Tuscany/FTX, custom conversions) trade in their own
# market and would drag every median upward.
HALO = ["رابتر", "رابتور", "raptor", "svt", "محول", "مجهز", "اوفرلاند", "شلبي", "ftx"]
PARTS = ["قطع غيار", "كتباك", "شمعه", "كبوت", "صدام", "جنوط", "اسطب", "دركسون",
         "مكينه", "مكينة", "عداد", "فرش", "دبه", "دبة", "بيماس", "كت ", "حماية",
         "وطايه", "واجهه", "مفتاح", "تربوئ", "ليد", "سماعه", "قماش", "رفرف",
         "شبك", "مرايا", "يايات", "دفريشن", "صندوق", "حوض", "قزاز", "بطاري"]
NEG_4WD = re.compile(
    r"(?:بدو+ن|غير|بلا|ما\s*ف[يى]ه|مافيه|مب|مو|ليس)\s*(?:دبل|4wd|4x4)")
CREW = ["غمارتين", "crew cab", "supercrew", "4 ابواب", "اربع ابواب", "4dr"]
SUPER = ["غماره ونص", "غمارة ونص", "supercab", "extended cab", "غماره ونصف",
         "غماره وربع", "غمارة و ربع"]
REG = ["غماره", "غمارة", "استاندر", "ستاندر", "regular cab", "single cab"]
V8 = ["v8", "ثمانيه سلندر", "8 سلندر", "ثماني سلندر", "5.0", "6.2", "8سلندر", "8 سرندل"]
V6 = ["v6", "سته سلندر", "6 سلندر", "ست سلندر", "3.7", "3.5", "6سلندر", "6 سرندل"]


def has(text, needles):
    return any(fold(n) in text for n in needles)


def load():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT * FROM posts WHERE status='live' AND (tags LIKE '%f150%' "
        "OR norm LIKE '%f150%' OR norm LIKE '%اف 150%')").fetchall()
    out = []
    for r in rows:
        t = " ".join([r["norm"] or "", fold(r["title"] or "")])
        if has(t, SOLD) or has(fold(r["title"] or ""), PARTS) or has(t, HALO):
            continue
        if r["kind"] not in ("CAR", ""):
            continue
        y = r["year"]
        if y is None or not (2011 <= y <= 2017):
            continue
        km = r["mileage"]
        km = None if (km and (km < 5_000 or km > 600_000)) else km
        p = r["price"]
        p = None if (p and not 10_000 <= p <= 400_000) else p
        out.append(dict(
            id=r["id"], y=y, km=km, p=p,
            w=0 if NEG_4WD.search(t) else (1 if (r["is_4wd"] == 1 or fold("دبل") in t
                                                 or "4x4" in t) else None),
            cab="crew" if has(t, CREW) else ("super" if has(t, SUPER)
                                             else ("reg" if has(t, REG) else "?")),
            eng="v8" if has(t, V8) else ("v6" if has(t, V6) else "?"),
            city=r["city"], seller=r["author"], title=r["title"], url=r["url"]))
    return out


def pct(values, x):
    values = sorted(values)
    return 100.0 * sum(1 for v in values if v < x) / len(values)


def is_four_door(c) -> bool:
    """SuperCab and crew cab both count as four-door and are never listed."""
    return c["cab"] in ("crew", "super")


def line(c, mark=""):
    km = f"{c['km']:,}" if c["km"] else "?"
    p = f"{c['p']:,}" if c["p"] else "no price"
    return (f"  {c['id']} {c['y']} cab={c['cab']:<5} 4wd={str(c['w']):<4} "
            f"{c['eng']:<3} {km:>8} km {p:>9} SAR  {(c['city'] or '')[:9]:<9}"
            f" | {(c['title'] or '')[:38]}{mark}")


def main():
    cars = load()
    tgt = next((c for c in cars if c["id"] == TARGET), None)
    if tgt is None:
        print(f"{TARGET} not in the mirror"); return
    print("TARGET"); print(line(tgt)); print()

    kms = [c["km"] for c in cars if c["km"]]
    ps = [c["p"] for c in cars if c["p"]]
    print(f"corpus: {len(cars)} F-150s 2011-2017 "
          f"({len(kms)} with mileage, {len(ps)} with a price)")
    print(f"  mileage  median {st.median(kms):,.0f} km   "
          f"target {tgt['km']:,} km = {pct(kms, tgt['km']):.0f}th percentile "
          f"(only {sum(1 for k in kms if k <= tgt['km'])} are lower)")
    same_year = [c["p"] for c in cars if c["p"] and c["y"] == tgt["y"]]
    print(f"  {tgt['y']} asking prices: n={len(same_year)} "
          f"median {st.median(same_year):,.0f}  target {tgt['p']:,} = "
          f"{pct(same_year, tgt['p']):.0f}th percentile")

    print(f"\nSAME PRICE, what else {tgt['p']-5000:,}-{tgt['p']+5000:,} SAR buys "
          f"({tgt['y']-1}-{tgt['y']+1}):")
    band = [c for c in cars if c["p"] and abs(c["p"] - tgt["p"]) <= 5_000
            and abs(c["y"] - tgt["y"]) <= 1 and not is_four_door(c)]
    for c in sorted(band, key=lambda c: c["km"] or 9e9):
        print(line(c, "   <-- TARGET" if c["id"] == TARGET else ""))

    print(f"\nSAME MILEAGE, what a {tgt['km']-30000:,}-{tgt['km']+30000:,} km "
          f"truck costs ({tgt['y']-1}-{tgt['y']+1}):")
    near = [c for c in cars if c["km"] and abs(c["km"] - tgt["km"]) <= 30_000
            and abs(c["y"] - tgt["y"]) <= 1 and not is_four_door(c)]
    for c in sorted(near, key=lambda c: c["p"] or 9e9):
        print(line(c, "   <-- TARGET" if c["id"] == TARGET else ""))

    print("\nSEGMENT PREMIUMS (2011-2017 asking prices):")
    for label, sel in [
        ("4WD دبل", lambda c: c["w"] == 1),
        ("2WD بدون دبل", lambda c: c["w"] == 0),
        ("regular cab غمارة", lambda c: c["cab"] == "reg"),
        ("supercab غمارة ونص", lambda c: c["cab"] == "super"),
        ("crew cab غمارتين", lambda c: c["cab"] == "crew"),
        ("V8", lambda c: c["eng"] == "v8"),
        ("V6", lambda c: c["eng"] == "v6"),
    ]:
        v = sorted(c["p"] for c in cars if c["p"] and sel(c))
        if len(v) >= 4:
            print(f"  {label:<22} n={len(v):>3}  median {st.median(v):>7,.0f}  "
                  f"p25 {v[len(v)//4]:>7,}  p75 {v[3*len(v)//4]:>7,}")


if __name__ == "__main__":
    main()
