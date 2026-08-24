"""Command line: poll / backfill / search / watch."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .crawl import Fetcher, fetch_ids, homepage_head, iter_search, iter_tag
from .store import Store


def _fmt_price(v: Any) -> str:
    return f"{v:,}" if v else "—"


def _fmt_km(v: Any) -> str:
    return f"{v:,}" if v else "—"


def _fmt_4wd(v: Any) -> str:
    return {1: "yes", 0: "no"}.get(v, "?")


def print_rows(rows) -> None:
    if not rows:
        print("(no results)")
        return
    for r in rows:
        print(f"{r['id']}  {r['year'] or '----'}  4wd={_fmt_4wd(r['is_4wd']):>3}  "
              f"km={_fmt_km(r['mileage']):>9}  {_fmt_price(r['price']):>9} SAR  "
              f"{(r['city'] or '')[:10]:<10}  {(r['title'] or '')[:56]}")
        print(f"    {r['url']}")


# --------------------------------------------------------------------------

def cmd_poll(args: argparse.Namespace) -> int:
    """High-water-mark poller.

    Post ids are sequential and dense (~25/min), so keeping up is a matter of
    walking `last_seen+1 .. head` -- not spidering.  Gaps are deleted or
    moderated posts; they are tombstoned and never retried.
    """
    store = Store(args.db)
    fetcher = Fetcher(rps=args.rps)
    try:
        head = homepage_head(fetcher)
        if not head:
            print("could not read head id from homepage", file=sys.stderr)
            return 1
        last = int(store.get_state("last_seen_id", "0") or 0)
        if last == 0:
            last = head - args.first_run_window
            print(f"first run: starting {args.first_run_window} ids back from head")
        start = last + 1
        if start > head:
            print(f"up to date at {head}")
            return 0
        todo = list(range(start, head + 1))[: args.max_posts]
        print(f"head={head} last_seen={last} fetching {len(todo)} ids")
        saved = gone = 0
        for i in range(0, len(todo), args.batch):
            chunk = todo[i:i + args.batch]
            got = fetch_ids(fetcher, chunk)
            for pid in chunk:
                post = got.get(pid)
                if post is None:
                    store.tombstone(pid)
                    gone += 1
                else:
                    store.upsert(post)
                    saved += 1
            store.set_state("last_seen_id", str(chunk[-1]))
            print(f"  ..{chunk[-1]}  saved={saved} tombstoned={gone}", flush=True)
        print(f"done: {saved} posts, {gone} tombstones")
        return 0
    finally:
        fetcher.close()
        store.close()


def cmd_backfill(args: argparse.Namespace) -> int:
    store = Store(args.db)
    fetcher = Fetcher(rps=args.rps)
    try:
        total = 0
        scopes = args.city or [None]
        jobs = [("tag", t) for t in args.tag] + [("search", q) for q in (args.search or [])]
        for kind, value in jobs:
            n = 0
            for city in scopes:
                walker = iter_tag if kind == "tag" else iter_search
                for post in walker(fetcher, value, max_pages=args.pages,
                                   limit=args.limit, city=city):
                    store.upsert(post)
                    n += 1
            print(f"{kind} {value!r}: {n} listings", flush=True)
            total += n
        print(f"total {total}")
        return 0
    finally:
        fetcher.close()
        store.close()


def cmd_search(args: argparse.Namespace) -> int:
    with Store(args.db) as store:
        rows = store.search(
            " ".join(args.query), exclude=args.exclude or "",
            max_price=args.max_price, min_year=args.min_year,
            max_year=args.max_year, max_km=args.max_km,
            min_price=args.min_price, require_price=args.require_price,
            require_year=args.require_year, limit=args.limit,
        )
        if args.json:
            print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
        else:
            print_rows(rows)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    with Store(args.db) as store:
        if args.action == "add":
            store.watch_add(
                args.name, q=args.q or "", exclude=args.exclude or "",
                max_price=args.max_price, min_year=args.min_year,
                max_year=args.max_year, max_km=args.max_km,
                min_price=args.min_price, require_price=args.require_price,
                require_year=args.require_year,
            )
            print(f"saved search '{args.name}'")
        elif args.action == "list":
            for row in store.watch_list():
                print(f"{row['name']}: q={row['q']!r} exclude={row['exclude']!r} "
                      f"max_price={row['max_price']} last_seen={row['last_seen']}")
        elif args.action == "rm":
            store.watch_remove(args.name)
            print(f"removed '{args.name}'")
        elif args.action == "check":
            names = [args.name] if args.name else [r["name"] for r in store.watch_list()]
            for name in names:
                rows = store.watch_check(name, advance=not args.no_advance)
                print(f"== {name}: {len(rows)} new")
                print_rows(rows)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m haraj.cli")
    ap.add_argument("--db", default="haraj.db")
    ap.add_argument("--rps", type=float, default=0.5,
                    help="requests/second ceiling (site tolerates 2; 0.5 keeps up)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("poll", help="fetch everything new since the last run")
    p.add_argument("--batch", type=int, default=40)
    p.add_argument("--max-posts", type=int, default=5000)
    p.add_argument("--first-run-window", type=int, default=500)
    p.set_defaults(func=cmd_poll)

    p = sub.add_parser("backfill", help="index one or more tag pages")
    p.add_argument("tag", nargs="*")
    p.add_argument("--search", action="append",
                   help="free-text query; repeat to sweep several. Reaches "
                        "listings Haraj never tagged.")
    p.add_argument("--pages", type=int, default=40)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--city", action="append",
                   help="scope the tag to a city; repeat to sweep several. "
                        "An unscoped tag query is not exhaustive.")
    p.set_defaults(func=cmd_backfill)

    p = sub.add_parser("search")
    p.add_argument("query", nargs="*")
    p.add_argument("--exclude", default="",
                   help="comma-separated PHRASES (not words) to exclude")
    p.add_argument("--max-price", type=int)
    p.add_argument("--min-year", type=int)
    p.add_argument("--max-year", type=int)
    p.add_argument("--max-km", type=int)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--min-price", type=int)
    p.add_argument("--require-price", action="store_true",
                   help="only listings that state a price (blank no longer passes)")
    p.add_argument("--require-year", action="store_true",
                   help="only listings with a known model year")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("watch")
    p.add_argument("action", choices=["add", "list", "rm", "check"])
    p.add_argument("name", nargs="?")
    p.add_argument("--q", default="")
    p.add_argument("--exclude", default="")
    p.add_argument("--max-price", type=int)
    p.add_argument("--min-year", type=int)
    p.add_argument("--max-year", type=int)
    p.add_argument("--max-km", type=int)
    p.add_argument("--min-price", type=int)
    p.add_argument("--require-price", action="store_true",
                   help="only listings that state a price (blank no longer passes)")
    p.add_argument("--require-year", action="store_true",
                   help="only listings with a known model year")
    p.add_argument("--no-advance", action="store_true")
    p.set_defaults(func=cmd_watch)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
