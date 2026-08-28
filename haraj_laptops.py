#!/usr/bin/env python3
"""
haraj_laptops.py - find fixed-price used laptops on haraj.com.sa that meet a
working spec (FORScan + Claude Code + Python tooling).

Two modes:

  --recon    Fetch a search page and report what came back (status, size, whether
             embedded JSON was found). Saves the raw body so the parser can be
             written against reality instead of guesswork. RUN THIS FIRST.

  (default)  Search, parse, filter out auction posts, score against the spec,
             print a ranked table.

Usage:
    python3 haraj_laptops.py --recon
    python3 haraj_laptops.py
    python3 haraj_laptops.py --term "ثينك باد" --max-price 1200

Requires: python3, requests  ->  pip install requests
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Run:  pip install requests")


BASE = "https://haraj.com.sa"
LEGACY = "https://legacy.haraj.com.sa"
OUT_DIR = "haraj_out"

# The legacy site is server-rendered PHP, so listings sit in the HTML itself -
# no JavaScript, no embedded-JSON hunting. Exact search paths are unverified,
# so recon tries each and reports which ones return usable listings.
SEARCH_PATTERNS = [
    LEGACY + "/search/{q}",
    LEGACY + "/index.php?s={q}",
    LEGACY + "/search.php?q={q}",
    LEGACY + "/tags/{q}",
    BASE + "/search/{q}",
]

# Haraj posts live at /<numeric id>/<slug>. This is stable across both the
# legacy and current sites and is the most reliable way to find listings
# without knowing the page's CSS structure.
POST_LINK_RE = re.compile(r'href="(?:https?://[^/"]+)?/(\d{7,})/([^"]*)"')

# Search terms that actually surface business-class machines rather than
# gaming rigs and MacBooks.
DEFAULT_TERMS = [
    "ثينك باد",
    "thinkpad",
    "لاتيتيود",
    "latitude",
    "elitebook",
    "لابتوب شركات",
]

CITY_TERMS = ["جدة", "جده", "jeddah"]

# A post with any of these and no explicit final price is an auction. Skip it.
AUCTION_MARKERS = ["السوم", "مزاد", "مزايدة", "للسوم", "المزاد"]
FINAL_PRICE_MARKERS = ["نهائي", "السعر نهائي", "سعر نهائي"]

SSD_MARKERS = ["ssd", "اس اس دي", "سسد", "إس إس دي"]
HDD_MARKERS = ["hdd", "هارد عادي", "قرص صلب عادي"]

# Minimum CPU generation. 8th gen is the Windows 11 cutoff for Intel.
MIN_CPU_GEN = 8
MIN_RAM_GB = 8

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.8",
}


def normalize(text: str) -> str:
    """Lowercase, convert Arabic-Indic digits, collapse whitespace."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.translate(ARABIC_DIGITS).lower()).strip()


def parse_cpu_generation(text: str) -> int | None:
    """
    Pull an Intel Core generation out of a model number.

    i5-8250U   -> 8       (4-digit model, generation is the leading digit)
    i7-10510U  -> 10      (5-digit model, generation is the leading two digits)
    i7-1165G7  -> 11      (4-digit with a G suffix is Ice Lake or newer, so the
                           generation is the leading two digits, not one)
    i5 8th gen -> 8
    """
    t = normalize(text)

    # Trailing suffix letters (U, H, G7, HQ...) are optional and must not be
    # required to sit on a word boundary - "8250u" has no boundary before "u".
    m = re.search(r"\bi[357][\s\-]?(\d{4,5})(g\d|[a-z]{0,2})", t)
    if m:
        model, suffix = m.group(1), m.group(2)
        if len(model) == 5:
            return int(model[:2])
        if suffix.startswith("g"):
            return int(model[:2])
        return int(model[0])

    m = re.search(r"(\d{1,2})\s*(?:th|nd|rd|st)?\s*gen", t)
    if m:
        return int(m.group(1))

    m = re.search(r"الجيل\s*(الثامن|التاسع|العاشر|الحادي عشر|الثاني عشر)", t)
    if m:
        return {
            "الثامن": 8, "التاسع": 9, "العاشر": 10,
            "الحادي عشر": 11, "الثاني عشر": 12,
        }[m.group(1)]

    return None


def parse_ram_gb(text: str) -> int | None:
    t = normalize(text)
    m = re.search(r"(\d{1,3})\s*(?:gb|جيجا|جيقا|قيقا|g)\b.{0,12}(?:ram|رام|ذاكرة)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:ram|رام|ذاكرة)\D{0,12}(\d{1,3})\s*(?:gb|جيجا|جيقا|قيقا|g)?", t)
    if m:
        return int(m.group(1))
    return None


def parse_price_sar(text: str) -> int | None:
    """Find a plausible SAR price. Returns None if nothing price-shaped is found."""
    t = normalize(text)
    candidates: list[int] = []

    for m in re.finditer(r"(\d[\d,\.]{1,8})\s*(?:ريال|sar|ر\.س|ريإل)", t):
        raw = m.group(1).replace(",", "").replace(".", "")
        if raw.isdigit():
            candidates.append(int(raw))

    for m in re.finditer(r"(?:السعر|سعر|price)\D{0,8}(\d[\d,\.]{1,8})", t):
        raw = m.group(1).replace(",", "").replace(".", "")
        if raw.isdigit():
            candidates.append(int(raw))

    # A laptop under 100 or over 20000 SAR is almost certainly a parsing artifact.
    candidates = [c for c in candidates if 100 <= c <= 20000]
    return min(candidates) if candidates else None


def has_any(text: str, markers: list[str]) -> bool:
    t = normalize(text)
    return any(normalize(mk) in t for mk in markers)


@dataclass
class Listing:
    title: str = ""
    body: str = ""
    url: str = ""
    city: str = ""
    price: int | None = None
    cpu_gen: int | None = None
    ram_gb: int | None = None
    has_ssd: bool = False
    is_auction: bool = False
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return f"{self.title} {self.body} {self.city}"


def evaluate(listing: Listing) -> Listing:
    """Score against the spec. Negative score means reject."""
    text = listing.text

    listing.price = listing.price or parse_price_sar(text)
    listing.cpu_gen = parse_cpu_generation(text)
    listing.ram_gb = parse_ram_gb(text)
    listing.has_ssd = has_any(text, SSD_MARKERS)
    listing.is_auction = has_any(text, AUCTION_MARKERS) and not has_any(
        text, FINAL_PRICE_MARKERS
    )

    score = 0
    reasons = []

    # Hard rejects.
    if listing.is_auction:
        listing.score = -100
        listing.reasons = ["auction / السوم - skipped"]
        return listing

    if listing.price is None:
        listing.score = -100
        listing.reasons = ["no fixed price stated"]
        return listing

    if listing.cpu_gen is not None and listing.cpu_gen < MIN_CPU_GEN:
        listing.score = -100
        listing.reasons = [f"CPU gen {listing.cpu_gen} < {MIN_CPU_GEN} (no Win11)"]
        return listing

    # Scoring.
    if listing.cpu_gen is None:
        reasons.append("CPU generation unknown - ask seller")
    elif listing.cpu_gen >= 10:
        score += 30
        reasons.append(f"gen {listing.cpu_gen}")
    else:
        score += 20
        reasons.append(f"gen {listing.cpu_gen}")

    if listing.ram_gb is None:
        reasons.append("RAM unknown - ask seller")
    elif listing.ram_gb >= 16:
        score += 20
        reasons.append(f"{listing.ram_gb}GB RAM")
    elif listing.ram_gb >= MIN_RAM_GB:
        score += 15
        reasons.append(f"{listing.ram_gb}GB RAM")
    else:
        score -= 20
        reasons.append(f"only {listing.ram_gb}GB RAM")

    if listing.has_ssd:
        score += 15
        reasons.append("SSD")
    elif has_any(text, HDD_MARKERS):
        score -= 15
        reasons.append("mechanical HDD")
    else:
        reasons.append("storage type unknown")

    t = normalize(text)
    for family, pts in (("thinkpad", 15), ("ثينك باد", 15), ("latitude", 12),
                        ("لاتيتيود", 12), ("elitebook", 12), ("probook", 5)):
        if family in t:
            score += pts
            reasons.append(family)
            break

    if any(normalize(c) in t for c in CITY_TERMS):
        score += 10
        reasons.append("Jeddah")

    # Cheaper is better, gently.
    if listing.price <= 700:
        score += 15
    elif listing.price <= 1000:
        score += 10
    elif listing.price <= 1500:
        score += 5

    listing.score = score
    listing.reasons = reasons
    return listing


def fetch(url: str, timeout: int = 25) -> requests.Response:
    return requests.get(url, headers=HEADERS, timeout=timeout)


def extract_embedded_json(html: str) -> dict | None:
    """
    Modern SPAs ship their data as JSON inside the HTML. Try the common shapes
    so we never need a real browser.
    """
    patterns = [
        r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r'<script[^>]*>\s*window\.__NUXT__\s*=\s*(.*?);?\s*</script>',
        r'<script[^>]*>\s*window\.__INITIAL_STATE__\s*=\s*(.*?);?\s*</script>',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    return None


def walk_for_listings(node, found: list[dict], depth: int = 0) -> None:
    """
    Recursively hunt for listing-shaped dicts in an unknown JSON structure.
    A listing looks like something with a title and an id.
    """
    if depth > 12:
        return
    if isinstance(node, dict):
        keys = {k.lower() for k in node.keys()}
        if ("title" in keys or "postTitle" in node) and ("id" in keys or "postId" in node):
            found.append(node)
        for v in node.values():
            walk_for_listings(v, found, depth + 1)
    elif isinstance(node, list):
        for v in node:
            walk_for_listings(v, found, depth + 1)


TAG_RE = re.compile(r"<[^>]+>")
ENTITY_RE = re.compile(r"&[a-z]+;|&#\d+;")


def strip_tags(html: str) -> str:
    """Crude but dependency-free HTML -> text."""
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.DOTALL | re.I)
    text = TAG_RE.sub(" ", text)
    text = ENTITY_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_listings_from_html(html: str, base: str) -> list[Listing]:
    """
    Pull listings out of a server-rendered page without knowing its CSS.

    Finds every /<id>/<slug> post link, then takes the HTML between that link
    and the next one as the listing's context - which is where the price, city
    and specs live. Structure-agnostic, so it survives layout changes.
    """
    matches = list(POST_LINK_RE.finditer(html))
    listings: list[Listing] = []
    seen: set[str] = set()

    for i, m in enumerate(matches):
        post_id, slug = m.group(1), m.group(2)
        if post_id in seen:
            continue
        seen.add(post_id)

        end = matches[i + 1].start() if i + 1 < len(matches) else m.end() + 800
        context = strip_tags(html[m.start():min(end, m.start() + 1500)])

        # The slug is a URL-encoded version of the title; decode as a fallback
        # for pages where the anchor text is an image or icon.
        try:
            slug_text = requests.utils.unquote(slug).replace("_", " ").strip("/ ")
        except Exception:
            slug_text = ""

        listings.append(
            Listing(
                title=(slug_text or context[:80]),
                body=context,
                url=f"{base}/{post_id}/",
            )
        )
    return listings


def recon(term: str) -> None:
    """Try every candidate search URL and report which ones actually work."""
    os.makedirs(OUT_DIR, exist_ok=True)
    q = requests.utils.quote(term)
    best: tuple[int, str, str] | None = None

    print(f"\n=== RECON for term: {term}\n")
    for pattern in SEARCH_PATTERNS:
        url = pattern.format(q=q)
        try:
            r = fetch(url)
        except Exception as e:
            print(f"  FAIL  {url}\n        {type(e).__name__}: {e}")
            continue

        found = extract_listings_from_html(r.text, LEGACY)
        prices = len(re.findall(r"ريال|SAR", r.text))
        has_json = extract_embedded_json(r.text) is not None

        print(f"  HTTP {r.status_code}  {len(r.text):>7}b  "
              f"listings={len(found):<4} prices={prices:<4} json={has_json}")
        print(f"        {url}")

        if r.status_code == 200 and (best is None or len(found) > best[0]):
            best = (len(found), url, r.text)
        time.sleep(1.0)

    if best is None:
        print("\n  Nothing reachable. Check your connection, then send me this output.")
        return

    count, url, body = best
    path = os.path.join(OUT_DIR, "recon_raw.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)

    print(f"\n  BEST: {url}  ({count} listings)")
    print(f"  Saved raw HTML -> {path}")

    if count:
        print("\n  Sample of what was parsed:")
        for lst in extract_listings_from_html(body, LEGACY)[:3]:
            ev = evaluate(lst)
            print(f"    - {lst.title[:60]}")
            print(f"      price={ev.price} gen={ev.cpu_gen} ram={ev.ram_gb} "
                  f"score={ev.score}")
        print("\n  Parsing works. Run without --recon to search for real.")
    else:
        print("\n  Page fetched but no listings parsed - the link format differs.")
        print("  Send me haraj_out/recon_raw.html and I'll fix the pattern.")


def search(term: str, pages: int = 1) -> list[Listing]:
    """Search every candidate URL pattern, keeping whatever yields listings."""
    listings: list[Listing] = []
    q = requests.utils.quote(term)

    for pattern in SEARCH_PATTERNS:
        for page in range(1, pages + 1):
            url = pattern.format(q=q)
            if page > 1:
                url += ("&" if "?" in url else "?") + f"page={page}"
            try:
                r = fetch(url)
            except Exception as e:
                print(f"  [{term}] {type(e).__name__}: {e}", file=sys.stderr)
                break
            if r.status_code != 200:
                break

            batch = extract_listings_from_html(r.text, LEGACY)

            # Fall back to embedded JSON if this is the modern SPA.
            if not batch:
                data = extract_embedded_json(r.text)
                if data:
                    raw: list[dict] = []
                    walk_for_listings(data, raw)
                    batch = [
                        Listing(
                            title=str(item.get("title") or ""),
                            body=str(item.get("bodyTEXT") or item.get("body") or ""),
                            city=str(item.get("city") or ""),
                            url=f"{BASE}/{item.get('id') or ''}/",
                        )
                        for item in raw
                    ]

            listings.extend(batch)
            time.sleep(1.5)  # be polite

        if listings:  # this pattern worked; no need to try the rest
            break

    return listings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recon", action="store_true",
                    help="probe the site and dump what comes back (run this first)")
    ap.add_argument("--term", action="append", help="search term (repeatable)")
    ap.add_argument("--pages", type=int, default=2, help="pages per term")
    ap.add_argument("--max-price", type=int, default=2000, help="SAR ceiling")
    args = ap.parse_args()

    terms = args.term or DEFAULT_TERMS

    if args.recon:
        recon(terms[0])
        return

    all_listings: list[Listing] = []
    for term in terms:
        print(f"searching: {term}", file=sys.stderr)
        all_listings.extend(search(term, args.pages))

    # Deduplicate by URL.
    seen: set[str] = set()
    unique: list[Listing] = []
    for lst in all_listings:
        if lst.url not in seen:
            seen.add(lst.url)
            unique.append(lst)

    scored = [evaluate(lst) for lst in unique]
    keep = [lst for lst in scored
            if lst.score > 0 and lst.price and lst.price <= args.max_price]
    keep.sort(key=lambda x: -x.score)

    if not keep:
        print("\nNo listings passed the filter.")
        print(f"Fetched {len(unique)} raw listings. If that is 0, run --recon.")
        return

    print(f"\n{'SAR':>7}  {'GEN':>4}  {'RAM':>4}  {'SCORE':>5}  TITLE")
    print("-" * 100)
    for lst in keep[:30]:
        print(f"{lst.price:>7}  {lst.cpu_gen or '?':>4}  {lst.ram_gb or '?':>4}  "
              f"{lst.score:>5}  {lst.title[:60]}")
        print(f"{'':>7}  {lst.url}")
        print(f"{'':>7}  {', '.join(lst.reasons)}")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "results.json"), "w", encoding="utf-8") as fh:
        json.dump([asdict(l) for l in keep], fh, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(keep)} results to {OUT_DIR}/results.json - send that to Claude.")


if __name__ == "__main__":
    main()
