# haraj — a local mirror of haraj.com.sa with Arabic-aware search

Python 3, SQLite, no services.

```
haraj/normalize.py   Arabic folding + synonyms + amount parsing
haraj/crawl.py       fetch + parse listing pages (GraphQL, HTML fallback)
haraj/store.py       SQLite + FTS5, search, saved searches
haraj/cli.py         poll / backfill / search / watch
analyze_f150.py      the F-150 hard-filter report built on top of the mirror
tests/               fixtures and tests
```

## Install

```bash
pip install 'httpx[http2]'      # the http2 extra is required
pip install pytest              # tests only
```

Plain `httpx` raises `ImportError` at client construction when `http2=True`.

## Use

```bash
python -m haraj.cli backfill "f150 2013" "f150 2014"   # index tag pages
python -m haraj.cli poll                               # keep up with new posts
python -m haraj.cli search f150 غمارة دبل --max-price 50000 \
    --exclude "بدون دبل, غمارتين"
python -m haraj.cli watch add f150 --q "f150 غمارة دبل" --max-price 50000 \
    --exclude "بدون دبل, غير دبل, غمارتين, غماره ونص, مطلوب, مصدوم"
python -m haraj.cli watch check f150                   # only genuinely new hits
```

`--rps` caps request rate (default 0.5/s; the site tolerates 2/s).

## There is a JSON API, and this uses it

**`https://graphql.haraj.com.sa/?queryName=search`** — unauthenticated, no
cookies, no client key. How it was found:

1. The homepage `<link rel="preconnect">` list names `graphql.haraj.com.sa`.
2. `POST {"query":"{__typename}"}` there returns `{"data":{"__typename":"Query"}}`.
   Introspection is disabled and errors are swallowed (empty 200 body), so the
   schema had to come from elsewhere.
3. The web client's own bundles are public. `useSearchQuery-*.js` carries the
   whole `Search` query verbatim, `useFetchAdsQuery-*.js` carries the
   `PostFields` fragment, and `fetcher-*.js` shows the endpoint takes the first
   selection name as a `?queryName=` parameter — which is why a bare POST to
   `/` returns nothing.

What that buys over HTML parsing:

* **Typed car fields.** `carInfo { is4DW model mileage fuel gear condition }`.
  4WD and mileage are structured values instead of prose to be guessed at.
* **Depth.** Server-rendered tag pages stop at ~21 listings and paginate
  client-side. The API paginates properly: `tags/f150 2013` yields 145.
* **Untruncated bodies.** `bodyTEXT` is the full post; `og:description` is not.

Both paths are implemented. `crawl.parse_listing()` is the HTML fallback and is
exercised by the test suite against a saved page, so the mirror keeps working if
the endpoint closes.

`pageInfo.hasNextPage` is always `true` on this endpoint; an empty page is the
only reliable terminator.

### HTML fallback details

Nothing is read from CSS classes — they change on redeploy. The fallback reads
`application/ld+json` (`@type: Thing` carries the full body and image list),
`og:` meta tags, and href shapes (`/city/X`, `/users/X`, `/tags/X`). The post
date comes from the `userfiles<N>/YYYY-MM-DD/` segment of the image URLs. The
body is *merged*, not chosen: the meta description holds the seller's prose, the
longest Arabic text run holds the attribute block Haraj prepends, and you want
both.

### Single cab only

`analyze_f150.py` drops any four-door body from the corpus **before any other
test**, so a crew cab (`غمارتين`) or SuperCab (`غمارة ونص`) can never reach the
report as a match, a near miss or an unknown. SuperCab counts as four-door: on
these model years its rear half-doors make it a 4dr body. `market_compare.py`
likewise never prints a four-door listing.

At the search layer the same rule is expressed as exclusion phrases, which is
exactly why they must stay comma-separated — see the phrase-exclusion note
below. `tests/test_store.py::TestSingleCabOnly` proves a four-door cannot come
back even from a query that matches it on every other term.

### Junk guards

Parts ads carry the same tags as the trucks and often name a placeholder price.
`--min-price`, `--require-price` and `--require-year` keep them out of search
and watch results without hand-maintained vocabulary:

```bash
python -m haraj.cli watch add f150 --q "f150 غمارة دبل" \
  --min-year 2011 --max-year 2017 --require-year \
  --max-km 200000 --min-price 15000 --max-price 50000 --require-price \
  --exclude "بدون دبل, غير دبل, غمارتين, غماره ونص, غماره ونصف, غماره وربع, 4 ابواب, مطلوب, مصدوم"
```

`--require-price` overrides the default that a blank price passes a
`--max-price` filter.

### Politeness

~0.5 req/s by default with jitter, exponential backoff on 429/5xx, and a real
contact address in the User-Agent. Keeping up with the live firehose
(~25 posts/min) needs about 0.5 req/s. Do not raise this.

## normalize.py

Folding runs identically at index time and query time, so the FTS layer never
needs to be Arabic-aware — plain `unicode61` tokenisation is enough.

Alef/ya/waw/ta-marbuta families collapse; Persian and Urdu lookalikes
(`ک ہ ھ ٹ ڈ پ`) fold to their Arabic equivalents, because real listings contain
them (`صيانہ آتو ميتک غسالات` is live); Arabic-Indic and Persian digits become
ASCII; diacritics, tatweel and zero-width characters are stripped; `ء` is
dropped; NFKC, lowercase, whitespace collapse.

Runs of 3+ identical characters collapse to 2 (`كثييييير` → `كثيير`). Doubles
are **not** collapsed — `الممملكة` → `الملكة` is a real collision. Digits are
**not** collapsed — `15000` must not become `1500`. Thousands separators are
stripped before punctuation handling so `15,000` survives, and decimal points
between digits are preserved so `1.5 مليون` does.

Synonyms live in a `{canonical: [variants]}` dict flattened into a bidirectional
lookup, matched on unigrams plus 2- and 3-grams so `لاند كروزر` works. The
expansion is stored in a **second** indexed column, never merged into `norm`, so
`bm25(posts_fts, 3.0, 1.0)` can weight exact spelling above synonym hits.

Amounts are **scored**, not taken in order. A listing body routinely contains a
year, a phone number, a mileage and a price in one paragraph
(`موديل 2012 … 0501234567 … ماشي 475الف … بسعر 45 ألف`). Each number is bound to
its nearest marker word, weighted by distance and preferring the preceding one,
with `الف`/`مليون` multipliers, phone-number stripping (including spaced forms
like `053 082 8812`), and rejection of bare 4-digit values in 1950–2035 unless a
currency marker attaches. Model numbers are excluded outright, so
`للبيع فورد اف 150` is not a 150,000 SAR truck.

### ⚠ Mileage is expressed in thousands

`mileage: 130 KM` in the attribute block, and `carInfo.mileage == 130` in the
API, both mean **130,000 km**. Taken literally every truck on the site looks
nearly new. Handled in `parse_block_mileage()` and `post_from_graphql()`, tested
in `tests/test_crawl.py`.

### ⚠ Absent 4WD is unknown, not 2WD

The `دبل` / `4WD` line only appears when the seller filled that field in.
Absence records `4wd = unknown`; nothing infers 2WD from it.

## store.py

`posts` + an FTS5 virtual table over `norm` and `norm_expanded`
(`content='posts'`, kept in sync by triggers). `dupe_key` hashes author + sorted
title tokens + price so a showroom relisting the same truck every morning
collapses to one row. Gaps in the id sequence are tombstoned (`status='gone'`)
and never retried. `saved_searches` carries a `last_seen` post-id watermark, so
`watch check` returns only genuinely new matches.

### ⚠ Exclusions are comma-separated phrases

```python
for phrase in exclude.split(","):
    bad = fold(phrase)
    if bad:
        where.append("p.norm NOT LIKE ?")
        args.append(f"%{bad}%")
```

This is load-bearing. Arabic negation is a **prefix**, so the negative phrase
*contains* the positive token: `بدون دبل` ("no 4WD") contains `دبل` ("4WD").
Split that on whitespace and you get `NOT LIKE %دبل%`, which silently excludes
every 4WD truck on the site — zero results, no error, the exact opposite of the
intent. `tests/test_store.py::TestPhraseExclusion` proves phrase exclusion keeps
the 4WD listings and drops the `بدون دبل` ones.

## Tests

```bash
python -m pytest tests/ -q
```

No network: the HTML parser is tested against a saved listing page in
`tests/fixtures/`.
