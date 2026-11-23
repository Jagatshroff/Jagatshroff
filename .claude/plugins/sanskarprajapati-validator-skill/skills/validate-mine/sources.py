#!/usr/bin/env python3
"""Mine complaints from free public sources into validator/complaints.jsonl.

  python3 sources.py reddit   --query '"unified inbox"' [--kind both|comment|post] [--subreddit S] [--since D] [--max N]
  python3 sources.py hn       --query '"unified inbox"' [--since D] [--max N]
  python3 sources.py appstore --app 6499013100 [--name Beeper] [--country us] [--max-rating 3]
  python3 sources.py find-app beeper
  python3 sources.py import   pasted.txt --name x
  python3 sources.py report

Global flags go first: --dir validator (state folder), --no-cache.
Reddit comes from the PullPush archive, Hacker News from Algolia, reviews from
Apple's public RSS. No keys. Every command adds to the store and logs the run.
"""

import argparse
import datetime
import json
import os
import re
import sys
from urllib.parse import quote, urlencode

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import store  # noqa: E402
from importer import read_import  # noqa: E402,F401  (re-exported for callers)
from minelog import REPORT, append_log, write_report  # noqa: E402
import netfetch  # noqa: E402
from netfetch import FetchError, Http  # noqa: E402,F401


def netfetch_wait_floor():
    return netfetch.RATE_LIMIT_WAIT

PULLPUSH = "https://api.pullpush.io/reddit/search/%s/?"
HN = "https://hn.algolia.com/api/v1/search_by_date?"
APP_REVIEWS = "https://itunes.apple.com/%s/rss/customerreviews/page=%d/id=%s/sortby=mostrecent/json"
APP_SEARCH = "https://itunes.apple.com/search?"
APP_PAGES = 10  # Apple serves at most 10 pages of 50 reviews
STOP = {"a", "an", "the", "of", "to", "for", "and", "or", "in", "on", "my", "i", "is", "it", "with"}
GONE = {"[deleted]", "[removed]"}
PARTIAL = 2  # exit code: some data saved, but the source stopped early


# Relevance --------------------------------------------------------------

def parse_query(query):
    """'"unified inbox" for recruiters' -> (['unified inbox'], ['recruiters'])."""
    phrases = [p.strip().lower() for p in re.findall(r'"([^"]+)"', query) if p.strip()]
    rest = re.sub(r'"[^"]*"', " ", query).lower()
    terms = [w for w in re.findall(r"[\w'+#.-]+", rest) if w not in STOP]
    return phrases, terms


def _hit(text, part):
    """Words in order, each starting a word. A short last word must be the whole word,
    so "ai" finds "AI" but not "aim"; longer ones may run on, so "inbox" finds "inboxes"."""
    words = part.split()
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(w) for w in words)
    if len(words[-1]) < 4:
        pattern += r"(?!\w)"
    return re.search(pattern, text) is not None


def matches(text, query, mode="all"):
    """Does text really talk about the query? Search APIs are fuzzy, so we check ourselves."""
    phrases, terms = parse_query(query)
    parts = phrases + terms
    if not parts:
        return True
    text = text.lower()
    found = [_hit(text, p) for p in parts]
    return any(found) if mode == "any" else all(found)


# Dates ------------------------------------------------------------------

def _day(epoch):
    return datetime.datetime.fromtimestamp(float(epoch), datetime.timezone.utc).date().isoformat()


def _epoch(day):
    try:
        moment = datetime.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        raise ValueError("dates are YYYY-MM-DD, got %r" % day)
    return int(moment.timestamp())


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


# Shared ----------------------------------------------------------------

BAD_ITEM = (ValueError, KeyError, TypeError, AttributeError)  # one malformed post is skipped, never fatal


def _field(data, key, source):
    if not isinstance(data, dict):
        raise FetchError("%s sent an unexpected response shape (%s)" % (source, type(data).__name__))
    return data.get(key)


def _result(out, raw, skipped, error, max_items):
    return {"records": out[:max_items], "raw": raw, "skipped": skipped, "error": error}


# Reddit, through PullPush -----------------------------------------------

def _reddit_url(item, kind):
    permalink = str(item.get("permalink") or "")
    if permalink.startswith("/") and not permalink.startswith("//"):
        return "https://www.reddit.com" + permalink
    if kind == "comment":  # rebuild from ids rather than trust an odd permalink
        return "https://www.reddit.com/comments/%s/_/%s/" % (str(item.get("link_id", ""))[3:], item["id"])
    return "https://www.reddit.com/comments/%s/" % item["id"]


def from_pullpush(item, kind, query):
    if store.is_bot(item.get("author")):
        return None  # AutoModerator reposts other people's words; a bot is never evidence
    if kind == "comment":
        body = (item.get("body") or "").strip()
        if body in GONE or not body:
            return None
        text, title = body, ""
    else:
        title = (item.get("title") or "").strip()
        body = (item.get("selftext") or "").strip()
        body = "" if body in GONE else body
        text = title + ("\n\n" + body if body else "")
        if not text:
            return None
    author = item.get("author") or ""
    score = item.get("score")
    return store.build_record(
        source="reddit", native_id=item["id"], url=_reddit_url(item, kind),
        text=text, created=_day(item["created_utc"]), author="" if author in GONE else author, title=title,
        score=score if isinstance(score, int) else None, community=item.get("subreddit") or "",
        kind="post" if kind == "post" else "comment", query=query, fetched=_now(),
    )


def _timestamp(item):
    try:
        return float(item["created_utc"])
    except BAD_ITEM:
        return None


def _reddit_kind(get_json, query, kind, opts, out, tally):
    endpoint = PULLPUSH % ("comment" if kind == "comment" else "submission")
    params = {"q": query, "size": 100, "sort": "desc", "sort_type": "created_utc"}
    if opts["subreddit"]:
        params["subreddit"] = opts["subreddit"]
    if opts["since"]:
        params["after"] = _epoch(opts["since"])
    before = None
    for _ in range(opts["max_pages"]):
        page = dict(params, **({"before": before} if before else {}))
        items = _field(get_json(endpoint + urlencode(page)), "data", "PullPush") or []
        if not items:
            return
        tally["raw"] += len(items)
        for item in items:
            try:
                record = from_pullpush(item, kind, query)
            except BAD_ITEM:
                tally["skipped"] += 1
                continue
            if record and matches(record["text"], query, opts["mode"]):
                out.append(record)
                if len(out) >= opts["max_items"]:
                    return
        stamps = [t for t in (_timestamp(i) for i in items if isinstance(i, dict)) if t is not None]
        oldest = int(min(stamps)) if stamps else None
        if oldest is None or (before is not None and oldest >= before):
            return  # the cursor stopped moving; the archive has nothing older for us
        before = oldest


def fetch_reddit(get_json, query, kind="both", subreddit=None, since=None, max_items=500, max_pages=10, mode="all"):
    opts = {"subreddit": subreddit, "since": since, "max_items": max_items, "max_pages": max_pages, "mode": mode}
    out, tally, error = [], {"raw": 0, "skipped": 0}, None
    try:
        for k in (["comment", "post"] if kind == "both" else [kind]):
            _reddit_kind(get_json, query, k, opts, out, tally)
            if len(out) >= max_items:
                break
    except FetchError as err:
        error = str(err)
    return _result(out, tally["raw"], tally["skipped"], error, max_items)


# Hacker News, through Algolia ---------------------------------------------

def from_hn(hit, query):
    if store.is_bot(hit.get("author")):
        return None
    tags = hit.get("_tags") or []
    if "comment" in tags:
        text, title, kind = hit.get("comment_text") or "", "", "comment"
    else:
        title = hit.get("title") or ""
        body = hit.get("story_text") or ""
        text, kind = title + ("\n\n" + body if body else ""), "post"
    if not store.clean_text(text):
        return None
    points = hit.get("points")
    return store.build_record(
        source="hn", native_id=hit["objectID"], url="https://news.ycombinator.com/item?id=%s" % hit["objectID"],
        text=text, created=hit.get("created_at") or _day(hit["created_at_i"]), author=hit.get("author") or "",
        title=title, score=points if isinstance(points, int) else None, community="hn", kind=kind,
        query=query, fetched=_now(),
    )


def fetch_hn(get_json, query, since=None, max_items=500, max_pages=10, mode="all"):
    params = {"query": query, "tags": "(story,comment)", "hitsPerPage": 100}
    if since:
        params["numericFilters"] = "created_at_i>%d" % _epoch(since)
    out, raw, skipped, error = [], 0, 0, None
    try:
        for number in range(max_pages):
            data = get_json(HN + urlencode(dict(params, page=number)))
            hits = _field(data, "hits", "Hacker News") or []
            raw += len(hits)
            for hit in hits:
                try:
                    record = from_hn(hit, query)
                except BAD_ITEM:
                    skipped += 1
                    continue
                if record and matches(record["text"], query, mode):
                    out.append(record)
            if len(out) >= max_items or not hits or number + 1 >= int(data.get("nbPages") or 0):
                break
    except FetchError as err:
        error = str(err)
    return _result(out, raw, skipped, error, max_items)


# App Store reviews --------------------------------------------------------

def _label(entry, key):
    return ((entry.get(key) or {}).get("label") or "").strip()


def from_review(entry, app_id, name, url):
    return store.build_record(
        source="appstore", native_id=_label(entry, "id"), url=url,
        text=_label(entry, "content"), created=_label(entry, "updated"),
        author=((entry.get("author") or {}).get("name") or {}).get("label", ""),
        title=_label(entry, "title"), rating=int(_label(entry, "im:rating")), community=name or app_id,
        kind="review", query="app:%s" % app_id, fetched=_now(),
    )


def fetch_appstore(get_json, app_id, name="", country="us", max_rating=3, max_items=500):
    app_id, country = str(app_id), str(country).lower()
    if not app_id.isdigit() or not re.match(r"^[a-z]{2}$", country):
        raise ValueError("app id must be digits and country a two-letter code, got %r / %r" % (app_id, country))
    url = "https://apps.apple.com/%s/app/id%s?see-all=reviews" % (country, app_id)
    out, raw, skipped, error = [], 0, 0, None
    try:
        for number in range(1, APP_PAGES + 1):
            feed = _field(get_json(APP_REVIEWS % (country, number, app_id)), "feed", "the App Store") or {}
            entries = _field(feed, "entry", "the App Store") or []
            entries = [entries] if isinstance(entries, dict) else entries
            if not entries:
                if number == 1:
                    error = ("Apple returned an empty review feed. It does this at times, even for "
                             "popular apps. Try again in an hour")
                break
            for entry in entries:
                try:
                    rating = _label(entry, "im:rating")
                    if not rating:
                        continue  # the app's own listing, not a review
                    raw += 1
                    if int(rating) <= max_rating and _label(entry, "content"):
                        out.append(from_review(entry, app_id, name, url))
                except BAD_ITEM:
                    skipped += 1
            if len(out) >= max_items:
                break
    except FetchError as err:
        error = str(err)
    return _result(out, raw, skipped, error, max_items)


def find_apps(get_json, term, country="us", limit=8):
    data = get_json(APP_SEARCH + urlencode({"term": term, "entity": "software", "limit": limit, "country": country}))
    return [{"id": str(r["trackId"]), "name": r.get("trackName", ""), "seller": r.get("sellerName", ""),
             "ratings": r.get("userRatingCount", 0), "average": r.get("averageUserRating")}
            for r in (_field(data, "results", "the App Store") or []) if isinstance(r, dict) and "trackId" in r]


# Command line -----------------------------------------------------------

def _parser():
    parser = argparse.ArgumentParser(description="Mine complaints from free public sources")
    parser.add_argument("--dir", default=store.DEFAULT_DIR, help="state folder (default: validator)")
    parser.add_argument("--no-cache", action="store_true", help="ignore the one-day response cache")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("reddit", "hn"):
        p = sub.add_parser(name)
        p.add_argument("--query", required=True)
        p.add_argument("--since", help="YYYY-MM-DD")
        p.add_argument("--max", type=int, default=500)
        p.add_argument("--match", choices=("all", "any"), default="all")
        if name == "reddit":
            p.add_argument("--kind", choices=("both", "comment", "post"), default="both")
            p.add_argument("--subreddit")
    p = sub.add_parser("appstore")
    p.add_argument("--app", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--country", default="us")
    p.add_argument("--max-rating", type=int, default=3)
    p.add_argument("--max", type=int, default=500)
    p = sub.add_parser("find-app")
    p.add_argument("term")
    p.add_argument("--country", default="us")
    p = sub.add_parser("import")
    p.add_argument("file")
    p.add_argument("--name", required=True, help="where it came from: x, g2, discord, survey...")
    sub.add_parser("report")
    return parser


def _run(args, http):
    if args.cmd == "reddit":
        return "reddit", args.query, fetch_reddit(http.get_json, args.query, args.kind, args.subreddit,
                                                  args.since, args.max, mode=args.match)
    if args.cmd == "hn":
        return "hn", args.query, fetch_hn(http.get_json, args.query, args.since, args.max, mode=args.match)
    if args.cmd == "appstore":
        fresh = Http(cache_dir=None)  # Apple's feed comes back empty at times; never cache that for a day
        return "appstore", "app:%s %s" % (args.app, args.name), fetch_appstore(
            fresh.get_json, args.app, args.name, args.country, args.max_rating, args.max)
    records, problems = read_import(args.file, args.name)
    for problem in problems[:10]:
        print("skipped %s" % problem, file=sys.stderr)
    return "import", "%s (%s)" % (os.path.basename(args.file), args.name), {
        "records": records, "raw": len(records) + len(problems), "skipped": len(problems), "error": None}


def main(argv=None):
    args = _parser().parse_args(argv)
    http = Http(cache_dir=None if args.no_cache else os.path.join(args.dir, "cache"))
    try:
        if args.cmd == "report":
            summary = write_report(args.dir)
            print("wrote %s: %d complaints" % (os.path.join(args.dir, REPORT), summary["total"]))
            return 0
        if args.cmd == "find-app":
            for app in find_apps(http.get_json, args.term, args.country):
                print("%-12s %-45s %s, %s ratings, avg %s" % (app["id"], app["name"][:45], app["seller"],
                                                              app["ratings"], app["average"]))
            return 0
        source, target, result = _run(args, http)
        added, dupes = store.add(os.path.join(args.dir, store.FILE), result["records"])
        entry = {"at": _now(), "source": source, "target": target, "raw": result["raw"],
                 "matched": len(result["records"]), "added": added, "dupes": dupes,
                 "skipped": result.get("skipped", 0), "error": result["error"]}
        append_log(args.dir, entry)
    except (ValueError, FetchError, OSError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 1
    print(json.dumps(entry))
    if result["error"]:
        print("warning: stopped early, kept what came in before: %s" % result["error"], file=sys.stderr)
        return PARTIAL
    return 0


if __name__ == "__main__":
    sys.exit(main())
