"""SQLite + FTS5 storage, search and saved searches.

Because `normalize.fold()` runs at write time, the FTS index never sees raw
Arabic -- `unicode61` tokenisation is sufficient and no Arabic analyser is
needed.  The same folding runs on the query side in `search()`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, Sequence

from .normalize import expand, fold, tokens

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS posts (
    id            INTEGER PRIMARY KEY,
    title         TEXT,
    body          TEXT,
    city          TEXT,
    author        TEXT,
    tags          TEXT,          -- JSON array
    price         INTEGER,       -- SAR, NULL = no price / على السوم
    mileage       INTEGER,       -- real kilometres, NOT the site's thousands
    images        TEXT,          -- JSON array
    n_images      INTEGER DEFAULT 0,
    posted_date   TEXT,          -- YYYY-MM-DD
    url           TEXT,
    fetched_at    INTEGER,
    status        TEXT DEFAULT 'live',   -- live | gone (tombstone)
    norm          TEXT,          -- folded title+body+tags
    norm_expanded TEXT,          -- synonym expansion, indexed separately
    dupe_key      TEXT,
    -- structured car fields, populated from the site's own typed fields
    year          INTEGER,
    is_4wd        INTEGER,       -- 1 yes / 0 no / NULL unknown
    gear          TEXT,
    fuel          TEXT,
    condition     TEXT,
    kind          TEXT,          -- CAR | RELATED (parts & accessories) | ''
    source        TEXT           -- graphql | html
);

CREATE INDEX IF NOT EXISTS posts_dupe    ON posts(dupe_key);
CREATE INDEX IF NOT EXISTS posts_status  ON posts(status);
CREATE INDEX IF NOT EXISTS posts_year    ON posts(year);

CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
    norm,
    norm_expanded,
    content='posts',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
    INSERT INTO posts_fts(rowid, norm, norm_expanded)
    VALUES (new.id, new.norm, new.norm_expanded);
END;

CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts BEGIN
    INSERT INTO posts_fts(posts_fts, rowid, norm, norm_expanded)
    VALUES ('delete', old.id, old.norm, old.norm_expanded);
END;

CREATE TRIGGER IF NOT EXISTS posts_au AFTER UPDATE ON posts BEGIN
    INSERT INTO posts_fts(posts_fts, rowid, norm, norm_expanded)
    VALUES ('delete', old.id, old.norm, old.norm_expanded);
    INSERT INTO posts_fts(rowid, norm, norm_expanded)
    VALUES (new.id, new.norm, new.norm_expanded);
END;

CREATE TABLE IF NOT EXISTS saved_searches (
    name       TEXT PRIMARY KEY,
    q          TEXT,
    exclude    TEXT,
    max_price  INTEGER,
    min_year   INTEGER,
    max_year   INTEGER,
    max_km     INTEGER,
    last_seen  INTEGER DEFAULT 0,   -- post-id watermark
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS crawl_state (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


@dataclass
class Post:
    id: int
    title: str = ""
    body: str = ""
    city: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    price: int | None = None
    mileage: int | None = None
    images: list[str] = field(default_factory=list)
    posted_date: str = ""
    url: str = ""
    status: str = "live"
    year: int | None = None
    is_4wd: int | None = None
    gear: str = ""
    fuel: str = ""
    condition: str = ""
    kind: str = ""
    source: str = "graphql"

    def searchable(self) -> str:
        return " ".join([self.title or "", self.body or "",
                         " ".join(self.tags or []), self.city or ""])

    def dupe_key(self) -> str:
        """Collapse the same showroom relisting the same truck every morning."""
        title_tokens = " ".join(sorted(set(tokens(self.title))))
        raw = f"{fold(self.author)}|{title_tokens}|{self.price if self.price else ''}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


class Store:
    def __init__(self, path: str = "haraj.db"):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        self.db.commit()
        self.db.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- writes ------------------------------------------------------------
    def upsert(self, post: Post) -> None:
        norm = fold(post.searchable())
        norm_expanded = expand(post.searchable())
        self.db.execute(
            """
            INSERT INTO posts (id, title, body, city, author, tags, price, mileage,
                               images, n_images, posted_date, url, fetched_at, status,
                               norm, norm_expanded, dupe_key, year, is_4wd, gear,
                               fuel, condition, kind, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, body=excluded.body, city=excluded.city,
                author=excluded.author, tags=excluded.tags, price=excluded.price,
                mileage=excluded.mileage, images=excluded.images,
                n_images=excluded.n_images, posted_date=excluded.posted_date,
                url=excluded.url, fetched_at=excluded.fetched_at,
                status=excluded.status, norm=excluded.norm,
                norm_expanded=excluded.norm_expanded, dupe_key=excluded.dupe_key,
                year=excluded.year, is_4wd=excluded.is_4wd, gear=excluded.gear,
                fuel=excluded.fuel, condition=excluded.condition,
                kind=excluded.kind, source=excluded.source
            """,
            (post.id, post.title, post.body, post.city, post.author,
             json.dumps(post.tags, ensure_ascii=False), post.price, post.mileage,
             json.dumps(post.images, ensure_ascii=False), len(post.images or []),
             post.posted_date, post.url, int(time.time()), post.status,
             norm, norm_expanded, post.dupe_key(), post.year, post.is_4wd,
             post.gear, post.fuel, post.condition, post.kind, post.source),
        )
        self.db.commit()

    def tombstone(self, post_id: int) -> None:
        """Record a gap (deleted / moderated post) so it is never retried."""
        self.db.execute(
            "INSERT INTO posts (id, status, fetched_at, norm, norm_expanded) "
            "VALUES (?, 'gone', ?, '', '') "
            "ON CONFLICT(id) DO UPDATE SET status='gone', fetched_at=excluded.fetched_at",
            (post_id, int(time.time())),
        )
        self.db.commit()

    def known_ids(self) -> set[int]:
        return {r[0] for r in self.db.execute("SELECT id FROM posts")}

    def get_state(self, key: str, default: str = "") -> str:
        row = self.db.execute("SELECT value FROM crawl_state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO crawl_state(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        self.db.commit()

    # -- search ------------------------------------------------------------
    def search(
        self,
        q: str = "",
        *,
        exclude: str = "",
        max_price: int | None = None,
        min_year: int | None = None,
        max_year: int | None = None,
        max_km: int | None = None,
        since_id: int | None = None,
        limit: int = 50,
        collapse_dupes: bool = True,
    ) -> list[sqlite3.Row]:
        where = ["p.status = 'live'"]
        args: list[Any] = []
        joins = ""
        order = "p.id DESC"
        select_extra = "0.0 AS score"

        qtokens = tokens(q)
        if qtokens:
            match = _match_expression(qtokens)
            joins = "JOIN posts_fts f ON f.rowid = p.id"
            where.append("posts_fts MATCH ?")
            args.append(match)
            # bm25 weights `norm` 3x over `norm_expanded`, so an exact-spelling
            # hit outranks a hit that only came in through a synonym.
            literal_bonus = " + ".join(
                ["(CASE WHEN p.norm LIKE ? THEN 1 ELSE 0 END)"] * len(qtokens)
            )
            select_extra = f"bm25(posts_fts, 3.0, 1.0) - 2.0 * ({literal_bonus}) AS score"
            order = "score ASC, p.id DESC"

        # ------------------------------------------------------------------
        # Exclusions are comma-separated PHRASES, never whitespace-split words.
        #
        # Arabic negation is a PREFIX, so the negative phrase contains the
        # positive token: `بدون دبل` ("no 4WD") contains `دبل` ("4WD").  Split
        # on whitespace and you get `NOT LIKE %دبل%`, which silently excludes
        # every 4WD truck on the site -- the exact opposite of the intent, with
        # no error and zero results.
        # ------------------------------------------------------------------
        for phrase in (exclude or "").split(","):
            bad = fold(phrase)
            if bad:
                where.append("p.norm NOT LIKE ?")
                args.append(f"%{bad}%")

        if max_price is not None:
            # No price at all counts as "no price listed" and passes.
            where.append("(p.price IS NULL OR p.price <= ?)")
            args.append(max_price)
        if min_year is not None:
            where.append("(p.year IS NULL OR p.year >= ?)")
            args.append(min_year)
        if max_year is not None:
            where.append("(p.year IS NULL OR p.year <= ?)")
            args.append(max_year)
        if max_km is not None:
            where.append("(p.mileage IS NULL OR p.mileage <= ?)")
            args.append(max_km)
        if since_id is not None:
            where.append("p.id > ?")
            args.append(since_id)

        sql = (f"SELECT p.*, {select_extra} FROM posts p {joins} "
               f"WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ?")

        # Argument order must follow the SQL text: MATCH, then the LIKE bonus
        # terms inside SELECT... sqlite binds in textual order, and SELECT comes
        # before WHERE, so rebuild the list accordingly.
        bound: list[Any] = []
        if qtokens:
            bound.extend(f"%{t}%" for t in qtokens)   # SELECT bonus
            bound.append(match)                       # WHERE MATCH
            bound.extend(args[1:])
        else:
            bound.extend(args)
        bound.append(limit * (4 if collapse_dupes else 1))

        rows = self.db.execute(sql, bound).fetchall()
        if collapse_dupes:
            rows = _collapse(rows)
        return rows[:limit]

    # -- saved searches ----------------------------------------------------
    def watch_add(self, name: str, **kw: Any) -> None:
        self.db.execute(
            "INSERT INTO saved_searches (name,q,exclude,max_price,min_year,max_year,"
            "max_km,last_seen,created_at) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET q=excluded.q, exclude=excluded.exclude,"
            " max_price=excluded.max_price, min_year=excluded.min_year,"
            " max_year=excluded.max_year, max_km=excluded.max_km",
            (name, kw.get("q", ""), kw.get("exclude", ""), kw.get("max_price"),
             kw.get("min_year"), kw.get("max_year"), kw.get("max_km"),
             kw.get("last_seen", 0), int(time.time())),
        )
        self.db.commit()

    def watch_list(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM saved_searches ORDER BY name").fetchall()

    def watch_remove(self, name: str) -> None:
        self.db.execute("DELETE FROM saved_searches WHERE name=?", (name,))
        self.db.commit()

    def watch_check(self, name: str, limit: int = 50, advance: bool = True):
        """Return only posts newer than the saved watermark, then advance it."""
        row = self.db.execute("SELECT * FROM saved_searches WHERE name=?", (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        hits = self.search(
            row["q"] or "", exclude=row["exclude"] or "", max_price=row["max_price"],
            min_year=row["min_year"], max_year=row["max_year"], max_km=row["max_km"],
            since_id=row["last_seen"] or 0, limit=limit,
        )
        if advance:
            # Advance to the highest id in the store, not just the highest hit,
            # so a second check reports nothing new.
            top = self.db.execute("SELECT COALESCE(MAX(id),0) FROM posts").fetchone()[0]
            self.db.execute("UPDATE saved_searches SET last_seen=? WHERE name=?",
                            (max(top, row["last_seen"] or 0), name))
            self.db.commit()
        return hits


def _match_expression(qtokens: Sequence[str]) -> str:
    """AND of per-token OR-groups: every query word must hit, in either column,
    either literally or through one of its synonyms."""
    from .normalize import LOOKUP
    groups = []
    for t in qtokens:
        members = sorted(LOOKUP.get(t, {t}) | {t})
        groups.append("(" + " OR ".join(f'"{m}"' for m in members) + ")")
    return " AND ".join(groups)


def _collapse(rows: Iterable[sqlite3.Row]) -> list[sqlite3.Row]:
    seen: set[str] = set()
    out = []
    for r in rows:
        k = r["dupe_key"]
        if k and k in seen:
            continue
        if k:
            seen.add(k)
        out.append(r)
    return out
