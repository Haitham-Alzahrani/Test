"""Fetching and parsing haraj.com.sa.

Two paths, in preference order:

1. **GraphQL** (`https://graphql.haraj.com.sa/?queryName=search`).  Haraj's own
   web client talks to this endpoint; it needs no authentication, it paginates
   far deeper than the server-rendered tag pages, and it returns the typed
   `carInfo` block (`is4DW`, `mileage`, `model`, `gear`, `fuel`, `condition`)
   that HTML only exposes as prose.  See README for how it was located.
2. **HTML** fallback, kept working because class names are not depended on:
   everything is read from `application/ld+json`, `og:` meta tags and href
   shapes, all of which survive redeploys.

Politeness: ~2 req/s ceiling with jitter, exponential backoff on 429/5xx, and
a real contact address in the User-Agent.  Keeping up with the live firehose
only needs about 0.5 req/s, which is the default.
"""

from __future__ import annotations

import html as htmlmod
import json
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

import httpx

from .normalize import fold, parse_block_mileage, parse_price
from .store import Post

BASE = "https://haraj.com.sa"
GRAPHQL = "https://graphql.haraj.com.sa/"

CONTACT = "haz8@yahoo.com"
USER_AGENT = f"HarajLocalMirror/1.0 (personal listing search; contact: {CONTACT})"

# The PostFields fragment as the site's own client requests it, trimmed to the
# fields this mirror stores.
_POST_FIELDS = """
fragment PostFields on Post {
  id
  title
  bodyTEXT
  postDate
  updateDate
  authorUsername
  URL
  city
  tags
  imagesList
  status
  price { formattedPrice inputPrice }
  carInfo { is4DW model mileage fuel gear condition carOrRelated sellOrWaiver }
}
"""

SEARCH_QUERY = """
query Search($search: String!, $tag: String, $city: String, $page: Int, $limit: Int) {
  search(search: $search, tag: $tag, city: $city, page: $page, limit: $limit) {
    items { ...PostFields }
    pageInfo { hasNextPage }
  }
}
""" + _POST_FIELDS

POSTS_QUERY = """
query FetchAds($id: [Int]) {
  posts(id: $id) {
    items { ...PostFields }
    pageInfo { hasNextPage }
  }
}
""" + _POST_FIELDS


class Fetcher:
    """Rate-limited, retrying HTTP client."""

    def __init__(self, rps: float = 0.5, timeout: float = 30.0, max_retries: int = 5):
        self.min_interval = 1.0 / rps if rps > 0 else 0.0
        self.max_retries = max_retries
        self._last = 0.0
        # The http2 extra is required; plain httpx raises ImportError here.
        self.client = httpx.Client(
            http2=True,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ar"},
            follow_redirects=True,
        )

    def _wait(self) -> None:
        gap = time.monotonic() - self._last
        delay = self.min_interval - gap
        if delay > 0:
            time.sleep(delay)
        time.sleep(random.uniform(0, 0.25))   # jitter
        self._last = time.monotonic()

    def request(self, method: str, url: str, **kw: Any) -> httpx.Response | None:
        for attempt in range(self.max_retries):
            self._wait()
            try:
                r = self.client.request(method, url, **kw)
            except httpx.HTTPError:
                time.sleep(2 ** attempt + random.random())
                continue
            if r.status_code in (429,) or r.status_code >= 500:
                time.sleep(2 ** attempt + random.random())
                continue
            return r
        return None

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any] | None:
        # The endpoint routes on ?queryName=, which is the first selection
        # inside the query body -- exactly how the site's own fetcher derives it.
        m = re.search(r"\{\s*\n\s*(\w+)", query)
        name = m.group(1) if m else "search"
        r = self.request(
            "POST", f"{GRAPHQL}?queryName={name}",
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
        )
        if r is None or r.status_code != 200 or not r.content:
            return None
        try:
            payload = r.json()
        except ValueError:
            return None
        if payload.get("errors"):
            return None
        return payload.get("data")

    def close(self) -> None:
        self.client.close()


# --------------------------------------------------------------------------
# GraphQL -> Post
# --------------------------------------------------------------------------

_LEADING_ID = re.compile(r"^/?(\d+)")


def _full_id(item: dict[str, Any]) -> int:
    """The API returns ids with the site-wide prefix stripped; the URL has it."""
    url = item.get("URL") or ""
    m = _LEADING_ID.match(url)
    if m:
        return int(m.group(1))
    return int(item["id"])


def _epoch_date(ts: Any) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def post_from_graphql(item: dict[str, Any]) -> Post:
    car = item.get("carInfo") or {}
    price_obj = item.get("price") or {}
    price = None
    raw_price = price_obj.get("inputPrice")
    if raw_price not in (None, "", "0"):
        try:
            price = int(float(raw_price))
        except (TypeError, ValueError):
            price = None
    # A placeholder price of 1 SAR means "على السوم" in practice; treat it as
    # no price rather than as an absurdly cheap truck.
    if price is not None and price <= 1:
        price = None

    body = item.get("bodyTEXT") or ""

    # ⚠ carInfo.mileage is expressed in THOUSANDS of kilometres, exactly like
    # the `mileage: 130 KM` line in the on-page attribute block.  Taken
    # literally, every truck on the site looks nearly new.
    mileage = None
    if car.get("mileage") is not None:
        try:
            mileage = int(float(car["mileage"]) * 1_000)
        except (TypeError, ValueError):
            mileage = None
    if mileage is None:
        from .normalize import parse_mileage
        mileage = parse_mileage(body)

    if price is None:
        price = parse_price(body)

    is_4wd = car.get("is4DW")
    if is_4wd is not None:
        is_4wd = 1 if is_4wd else 0

    pid = _full_id(item)
    url_path = item.get("URL") or f"{pid}/"
    return Post(
        id=pid,
        title=item.get("title") or "",
        body=body,
        city=item.get("city") or "",
        author=item.get("authorUsername") or "",
        tags=list(item.get("tags") or []),
        price=price,
        mileage=mileage,
        images=list(item.get("imagesList") or []),
        posted_date=_epoch_date(item.get("postDate")),
        url=f"{BASE}/{url_path.lstrip('/')}",
        status="live",
        year=car.get("model"),
        is_4wd=is_4wd,
        gear=car.get("gear") or "",
        fuel=car.get("fuel") or "",
        condition=car.get("condition") or "",
        # CAR vs RELATED separates actual trucks from the bumpers, exhausts and
        # headlights that carry the very same tags.
        kind=car.get("carOrRelated") or "",
        source="graphql",
    )


def iter_search(fetcher: Fetcher, term: str, max_pages: int = 40,
                limit: int = 50, city: str | None = None) -> Iterator[Post]:
    """Free-text search.

    Complements the tag sweep: tags only carry what Haraj's own classifier
    assigned, so a mistyped or untagged listing is reachable only this way.
    """
    return iter_tag(fetcher, tag=None, max_pages=max_pages, limit=limit,
                    city=city, search=term)


def iter_tag(fetcher: Fetcher, tag: str | None, max_pages: int = 40,
             limit: int = 50, city: str | None = None,
             search: str = "") -> Iterator[Post]:
    """Page through a tag until the API stops returning rows.

    `pageInfo.hasNextPage` is always true on this endpoint, so an empty page is
    the only reliable terminator.

    An unscoped tag query is *not* exhaustive -- paging `f150` to exhaustion
    yields ~1,000 rows, but re-running the same tag scoped to a city surfaces
    listings the unscoped pass never returned.  Pass `city` and sweep the city
    list to get full coverage.
    """
    seen: set[int] = set()
    for page in range(1, max_pages + 1):
        variables = {"search": search, "page": page, "limit": limit}
        if tag:
            variables["tag"] = tag
        if city:
            variables["city"] = city
        data = fetcher.graphql(SEARCH_QUERY, variables)
        if not data:
            return
        items = (data.get("search") or {}).get("items") or []
        if not items:
            return
        fresh = 0
        for item in items:
            pid = _full_id(item)
            if pid in seen:
                continue
            seen.add(pid)
            fresh += 1
            yield post_from_graphql(item)
        if fresh == 0:
            return


def fetch_ids(fetcher: Fetcher, ids: list[int]) -> dict[int, Post]:
    """Fetch specific post ids in one round trip (used by the poller)."""
    if not ids:
        return {}
    # The API keys on the prefix-stripped id.
    short = [int(str(i)[2:]) if len(str(i)) > 9 else int(i) for i in ids]
    data = fetcher.graphql(POSTS_QUERY, {"id": short})
    if not data:
        return {}
    out = {}
    for item in (data.get("posts") or {}).get("items") or []:
        p = post_from_graphql(item)
        out[p.id] = p
    return out


def homepage_head(fetcher: Fetcher) -> int:
    """Highest live post id, read off the homepage."""
    r = fetcher.request("GET", BASE + "/")
    if r is None:
        return 0
    ids = [int(x) for x in re.findall(r'href="/(\d{9,12})/', r.text)]
    return max(ids) if ids else 0


# --------------------------------------------------------------------------
# HTML fallback
# --------------------------------------------------------------------------

_LD = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_META = re.compile(r'<meta[^>]+property="(og:[a-z_]+)"[^>]+content="([^"]*)"', re.I)
_TAGS = re.compile(r'href="[^"]*/tags/([^"?]+)"')
_CITY = re.compile(r'href="[^"]*/city/([^"?]+)"')
_USER = re.compile(r'href="[^"]*/users/([^"?]+)"')
_IMG = re.compile(r'https://[a-z0-9]*cdn\.haraj\.com\.sa/userfiles\d*/(\d{4}-\d{2}-\d{2})/[^"\s\\]+')
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_NEXT_F = re.compile(r'self\.__next_f\.push\(')
_ARABIC = re.compile(r"[؀-ۿ]")
_TITLE_SUFFIX = " | موقع حراج"


def _unquote(s: str) -> str:
    # Underscores are meaningful inside tag and user slugs (`الرياض_f150 2013`,
    # `abu_fatema2026`), so they are left alone.
    from urllib.parse import unquote
    return unquote(s)


def _text_runs(page: str) -> list[str]:
    """Visible text, one entry per element, with markup stripped."""
    s = re.sub(r"(?is)<(script|style|noscript|nav|footer|header)[^>]*>.*?</\1>", " ", page)
    s = re.sub(r"(?s)<[^>]+>", "\n", s)
    s = htmlmod.unescape(s)
    return [ln.strip() for ln in s.split("\n") if ln.strip()]


def parse_listing(page: str, post_id: int) -> Post | None:
    """Parse a listing page from meta tags, ld+json and href shapes only."""
    # Prefer the page's own JSON when it ships any.
    ld_desc = ld_title = ""
    ld_images: list[str] = []
    for m in _LD.finditer(page):
        try:
            obj = json.loads(m.group(1).strip())
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("@type") == "Thing":
            ld_title = obj.get("name") or ""
            ld_desc = htmlmod.unescape(obj.get("description") or "")
            imgs = obj.get("image")
            ld_images = list(imgs) if isinstance(imgs, list) else ([imgs] if imgs else [])
            break

    nd = _NEXT_DATA.search(page)
    if nd and not ld_desc:
        try:
            blob = json.dumps(json.loads(nd.group(1)), ensure_ascii=False)
            hit = re.search(r'"bodyTEXT":"(.*?)","', blob)
            if hit:
                ld_desc = hit.group(1).encode().decode("unicode_escape")
        except ValueError:
            pass

    meta = {k.lower(): htmlmod.unescape(v) for k, v in _META.findall(page)}
    title = ld_title or meta.get("og:title", "")
    if title.endswith(_TITLE_SUFFIX):
        title = title[: -len(_TITLE_SUFFIX)]
    if not title:
        return None

    # Body recovery.  og:description carries the seller's prose but is often
    # truncated; the longest Arabic-bearing text run carries the structured
    # attribute block that og:description omits entirely.  Merge, don't pick.
    runs = _text_runs(page)
    arabic_runs = [r for r in runs if _ARABIC.search(r)]
    longest = max(arabic_runs, key=len) if arabic_runs else ""
    block = _attribute_block(runs, title)
    parts = [p for p in (block, ld_desc or meta.get("og:description", ""), longest) if p]
    seen_parts: list[str] = []
    for p in parts:
        if not any(p in q for q in seen_parts):
            seen_parts.append(p)
    body = "\n".join(seen_parts)

    tags = [_unquote(t) for t in dict.fromkeys(_TAGS.findall(page))]
    city_m = _CITY.search(page)
    user_m = _USER.search(page)

    images = ld_images or list(dict.fromkeys(m.group(0) for m in _IMG.finditer(page)))
    dates = _IMG.findall(page)
    posted = dates[0] if dates else ""

    combined = f"{title}\n{body}"
    mileage = parse_block_mileage(block) or parse_block_mileage(body)
    if mileage is None:
        from .normalize import parse_mileage
        mileage = parse_mileage(combined)

    return Post(
        id=post_id,
        title=title,
        body=body,
        city=_unquote(city_m.group(1)) if city_m else "",
        author=_unquote(user_m.group(1)) if user_m else "",
        tags=tags,
        price=parse_price(combined),
        mileage=mileage,
        images=images,
        posted_date=posted,
        url=f"{BASE}/{post_id}/",
        status="live",
        year=_year_from(combined),
        is_4wd=_4wd_from(block or combined),
        source="html",
    )


_ATTR_HINTS = ("قير", "بنزين", "ديزل", "الممشى", "mileage", "automatic", "gasoline",
               "دبل", "4wd", "مستخدم", "used", "new", "جديد")


def _attribute_block(runs: list[str], title: str) -> str:
    """The structured block Haraj prepends to car listings.

    Arabic pages render it as e.g.

        كرايزلر C300 2017 مستخدم
        قير اوتماتيك
        بنزين
        الممشى: 260 ألف كيلو
        دبل
    """
    picked = []
    for r in runs:
        low = fold(r)
        if len(r) <= 60 and any(fold(h) in low for h in _ATTR_HINTS):
            picked.append(r)
    return "\n".join(picked[:8])


def _year_from(text: str) -> int | None:
    years = [int(y) for y in re.findall(r"\b(19[5-9]\d|20[0-3]\d)\b", fold(text))]
    return max(years) if years else None


# Negation is a prefix in Arabic, and sellers stretch it for emphasis
# (`الموتر بدووون دبل`), which folding leaves as `بدوون`.  Matching a fixed
# `بدون دبل` string misses those and flips a 2WD truck into a 4WD one.
_NEG_4WD = re.compile(
    r"(?:بدو+ن|غير|بلا|ما\s*ف[يى]ه|مافيه|مب|مو|ليس|من\s+غير)\s*(?:دبل|4wd|4x4)"
)


def _4wd_from(text: str) -> int | None:
    """1 = 4WD, 0 = explicitly 2WD, None = unknown.

    ⚠ Absence of the 4WD line means the seller left the field blank.  It is
    never evidence of 2WD.
    """
    f = fold(text)
    if _NEG_4WD.search(f):
        return 0
    if fold("دبل") in f or "4wd" in f or "4x4" in f:
        return 1
    return None


def fetch_listing(fetcher: Fetcher, post_id: int) -> Post | None:
    r = fetcher.request("GET", f"{BASE}/{post_id}/")
    if r is None or r.status_code == 404:
        return None
    return parse_listing(r.text, post_id)
