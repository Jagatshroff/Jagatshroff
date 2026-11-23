import io
import json
import os
import tempfile
import unittest
import urllib.error
from urllib.parse import parse_qs, urlparse

from _load import FIXTURES, load

sources = load("validate-mine", "sources")
store = load("validate-mine", "store")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


class Router:
    """A fake get_json: serves fixtures by URL and records every call."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url):
        self.calls.append(url)
        for needle, payload in self.routes:
            if needle in url:
                return payload(url) if callable(payload) else payload
        raise AssertionError("unexpected url " + url)


class Query(unittest.TestCase):
    def test_phrases_and_terms(self):
        self.assertEqual(sources.parse_query('"unified inbox" for recruiters'), (["unified inbox"], ["recruiters"]))

    def test_all_mode_needs_every_part(self):
        q = '"unified inbox" whatsapp'
        self.assertTrue(sources.matches("My Unified  Inbox drops WhatsApp daily", q))
        self.assertFalse(sources.matches("unified, and an inbox, and whatsapp", q))
        self.assertFalse(sources.matches("a unified inbox without the other app", q))

    def test_terms_match_word_starts(self):
        self.assertTrue(sources.matches("so many inboxes", "inbox"))
        self.assertFalse(sources.matches("sandbox", "box"))

    def test_any_mode(self):
        self.assertTrue(sources.matches("only slack here", "slack teams", mode="any"))
        self.assertFalse(sources.matches("only email here", "slack teams", mode="any"))

    def test_empty_query_matches_everything(self):
        self.assertTrue(sources.matches("anything", ""))

    def test_non_latin_query(self):
        self.assertTrue(sources.matches("Этот мессенджер ужасен", "мессенджер"))
        self.assertFalse(sources.matches("совсем другое", "мессенджер"))

    def test_short_terms_need_the_whole_word(self):
        self.assertTrue(sources.matches("an AI tool", "ai"))
        self.assertFalse(sources.matches("I said no, aim higher", "ai"))

    def test_terms_starting_with_symbols(self):
        self.assertTrue(sources.matches("we moved to .net last year", ".net"))
        self.assertTrue(sources.matches("same issue +1", "+1"))


class Reddit(unittest.TestCase):
    def test_parses_comments_and_posts(self):
        get = Router([("/comment/", fixture("pullpush_comments.json")),
                      ("/submission/", fixture("pullpush_submissions.json"))])
        result = sources.fetch_reddit(get, '"unified inbox"', max_pages=1)
        by_native = {r["native_id"]: r for r in result["records"]}
        self.assertEqual(sorted(by_native), ["c1", "s1", "s2"])  # c2 removed, c3 off topic
        self.assertEqual(result["raw"], 5)
        c1 = by_native["c1"]
        self.assertEqual(c1["url"], "https://www.reddit.com/r/beeper/comments/p1/t/c1/")
        self.assertEqual((c1["community"], c1["kind"], c1["score"], c1["created"]), ("beeper", "comment", 14, "2026-10-09"))
        self.assertEqual(by_native["s1"]["text"], "Is there a unified inbox for LinkedIn and email?")
        self.assertIn("Instagram flagged", by_native["s2"]["text"])
        self.assertEqual(by_native["s2"]["kind"], "post")

    def test_paginates_with_before_cursor(self):
        pages = [fixture("pullpush_comments.json"), {"data": []}]

        def page(url):
            return pages.pop(0)

        get = Router([("/comment/", page)])
        sources.fetch_reddit(get, "inbox", kind="comment", max_pages=5)
        self.assertEqual(len(get.calls), 2)
        second = parse_qs(urlparse(get.calls[1]).query)
        self.assertEqual(second["before"], ["1791550000"])

    def test_stops_when_cursor_does_not_move(self):
        get = Router([("/comment/", fixture("pullpush_comments.json"))])
        sources.fetch_reddit(get, "inbox", kind="comment", max_pages=9)
        self.assertEqual(len(get.calls), 2)

    def test_passes_filters(self):
        get = Router([("/comment/", {"data": []})])
        sources.fetch_reddit(get, "inbox", kind="comment", subreddit="beeper", since="2026-01-01")
        q = parse_qs(urlparse(get.calls[0]).query)
        self.assertEqual((q["subreddit"], q["after"], q["size"]), (["beeper"], ["1767225600"], ["100"]))

    def test_respects_max_items(self):
        get = Router([("/comment/", fixture("pullpush_comments.json")), ("/submission/", fixture("pullpush_submissions.json"))])
        self.assertEqual(len(sources.fetch_reddit(get, "unified inbox", max_items=2, max_pages=1)["records"]), 2)

    def test_bad_items_are_skipped_not_fatal(self):
        page = {"data": [{"id": "x1", "body": "unified inbox but no date", "permalink": "/r/a/x1/"},
                         {"body": "unified inbox but no id", "created_utc": 1791559869.0},
                         {"id": "ok", "body": "a unified inbox that works", "created_utc": 1791559869.0,
                          "permalink": "/r/a/ok/", "score": "n/a"}]}
        pages = [page, {"data": []}]
        result = sources.fetch_reddit(Router([("/comment/", lambda u: pages.pop(0))]), "unified inbox", kind="comment")
        self.assertEqual([r["native_id"] for r in result["records"]], ["ok"])
        self.assertEqual(result["skipped"], 2)
        self.assertIsNone(result["error"])

    def test_unexpected_shape_is_an_error(self):
        result = sources.fetch_reddit(Router([("/comment/", ["not", "a", "dict"])]), "x", kind="comment")
        self.assertEqual(result["records"], [])
        self.assertIn("unexpected", result["error"])

    def test_bot_posts_are_dropped(self):
        page = {"data": [{"id": "b1", "author": "AutoModerator", "body": "unified inbox weekly thread copy",
                          "created_utc": 1791559869.0, "permalink": "/r/a/b1/"},
                         {"id": "b2", "author": "human_one", "body": "my unified inbox broke again",
                          "created_utc": 1791559869.0, "permalink": "/r/a/b2/"}]}
        pages = [page, {"data": []}]
        result = sources.fetch_reddit(Router([("/comment/", lambda u: pages.pop(0))]), "unified inbox", kind="comment")
        self.assertEqual([r["native_id"] for r in result["records"]], ["b2"])

    def test_permalink_must_be_a_path(self):
        page = {"data": [{"id": "e1", "body": "unified inbox", "created_utc": 1791559869.0,
                          "permalink": "@evil.example/x", "link_id": "t3_p9"}]}
        pages = [page, {"data": []}]
        result = sources.fetch_reddit(Router([("/comment/", lambda u: pages.pop(0))]), "unified inbox", kind="comment")
        self.assertEqual(result["records"][0]["url"], "https://www.reddit.com/comments/p9/_/e1/")

    def test_error_keeps_partial_results(self):
        calls = {"n": 0}

        def flaky(url):
            calls["n"] += 1
            if calls["n"] > 1:
                raise sources.FetchError("HTTP 503")
            return fixture("pullpush_comments.json")

        result = sources.fetch_reddit(Router([("/comment/", flaky)]), "unified inbox", kind="comment", max_pages=3)
        self.assertEqual(len(result["records"]), 1)
        self.assertIn("503", result["error"])


class HackerNews(unittest.TestCase):
    def test_parses_hits_and_filters(self):
        get = Router([("hn.algolia.com", fixture("hn_page.json"))])
        result = sources.fetch_hn(get, '"unified inbox"')
        by_native = {r["native_id"]: r for r in result["records"]}
        self.assertEqual(sorted(by_native), ["101", "102"])
        self.assertEqual(by_native["101"]["text"],
                         'I built my own unified inbox script because nothing else handled "who do I owe a reply".\nTook a weekend.')
        self.assertEqual(by_native["101"]["url"], "https://news.ycombinator.com/item?id=101")
        self.assertEqual(by_native["102"]["text"], "Ask HN: Anyone happy with a unified inbox?\n\nLooking for one that covers Slack and email.")
        self.assertEqual((by_native["102"]["kind"], by_native["102"]["score"]), ("post", 12))

    def test_since_becomes_numeric_filter(self):
        get = Router([("hn.algolia.com", {"nbPages": 0, "hits": []})])
        sources.fetch_hn(get, "inbox", since="2026-01-01")
        self.assertIn("created_at_i>1767225600", parse_qs(urlparse(get.calls[0]).query)["numericFilters"])


class HackerNewsBadData(unittest.TestCase):
    def test_hit_without_id_is_skipped(self):
        page = {"nbPages": 1, "hits": [{"comment_text": "unified inbox", "_tags": ["comment"]},
                                       {"objectID": "7", "comment_text": "unified inbox pain",
                                        "created_at": "2026-01-01T00:00:00Z", "_tags": ["comment"]}]}
        result = sources.fetch_hn(Router([("hn.algolia.com", page)]), "unified inbox")
        self.assertEqual(([r["native_id"] for r in result["records"]], result["skipped"]), (["7"], 1))


class AppStore(unittest.TestCase):
    def test_keeps_low_ratings_only(self):
        get = Router([("page=1/", fixture("appstore_page.json")), ("page=2/", {"feed": {}})])
        result = sources.fetch_appstore(get, "6499013100", name="Beeper")
        self.assertEqual([r["native_id"] for r in result["records"]], ["9001", "9003"])
        r = result["records"][0]
        self.assertEqual((r["rating"], r["title"], r["community"], r["created"]), (2, "Banned on WhatsApp", "Beeper", "2026-10-23"))
        self.assertEqual(r["url"], "https://apps.apple.com/us/app/id6499013100?see-all=reviews")

    def test_max_rating_five_keeps_all(self):
        get = Router([("page=1/", fixture("appstore_page.json")), ("page=2/", {"feed": {}})])
        self.assertEqual(len(sources.fetch_appstore(get, "1", max_rating=5)["records"]), 3)

    def test_single_entry_dict(self):
        get = Router([("page=1/", fixture("appstore_single.json")), ("page=2/", {"feed": {}})])
        self.assertEqual(len(sources.fetch_appstore(get, "1")["records"]), 1)

    def test_empty_feed_is_reported(self):
        result = sources.fetch_appstore(Router([("page=1/", {"feed": {"title": {"label": "x"}}})]), "1")
        self.assertEqual(result["records"], [])
        self.assertIn("empty", result["error"])

    def test_rejects_bad_app_id(self):
        with self.assertRaises(ValueError):
            sources.fetch_appstore(Router([]), "../etc")

    def test_find_app(self):
        get = Router([("itunes.apple.com/search", fixture("appsearch.json"))])
        apps = sources.find_apps(get, "beeper")
        self.assertEqual(apps[0], {"id": "6499013100", "name": "Beeper: Every Chat in One App", "seller": "Automattic",
                                   "ratings": 1200, "average": 3.9})


class Import(unittest.TestCase):
    def test_text_blocks_with_metadata(self):
        records, _ = sources.read_import(os.path.join(FIXTURES, "import_posts.txt"), name="x", today="2026-10-26")
        self.assertEqual(len(records), 2)
        first, second = records
        self.assertEqual((first["url"], first["author"], first["created"]), ("https://x.com/someone/status/1", "@someone", "2026-10-20"))
        self.assertEqual(first["text"], "I need one place where I can see every DM I owe a reply to.\n\nIt is driving me nuts.")
        self.assertEqual((second["url"], second["created"], second["community"]), ("import_posts.txt#2", "2026-10-26", "x"))

    def test_csv_with_excel_bom(self):
        path = os.path.join(tempfile.mkdtemp(), "bom.csv")
        with open(path, "w", encoding="utf-8-sig") as fh:
            fh.write("text,url\nslow and buggy,https://x.test/1\n")
        records, _ = sources.read_import(path, name="g2", today="2026-10-26")
        self.assertEqual(records[0]["text"], "slow and buggy")

    def test_bad_rows_are_skipped_with_row_numbers(self):
        path = os.path.join(tempfile.mkdtemp(), "rows.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"text": 12345}) + "\n")
            fh.write(json.dumps({"text": "fine row", "date": "March 3"}) + "\n")
            fh.write(json.dumps({"text": "good row", "score": "1,234", "author": ["x"]}) + "\n")
        records, skipped = sources.read_import(path, name="s", today="2026-10-26")
        self.assertEqual([r["text"] for r in records], ["12345", "good row"])
        self.assertEqual(records[1]["score"], 1234)
        self.assertEqual(records[1]["author"], "")
        self.assertEqual(len(skipped), 1)
        self.assertIn("row 2", skipped[0])

    def test_csv_skips_empty_rows(self):
        records, skipped = sources.read_import(os.path.join(FIXTURES, "import_rows.csv"), name="g2", today="2026-10-26")
        self.assertEqual(len(records), 1)
        self.assertEqual((records[0]["title"], records[0]["url"]), ("Too many tools", "https://g2.com/r/1"))

    def test_jsonl(self):
        records, _ = sources.read_import(os.path.join(FIXTURES, "import_rows.jsonl"), name="survey", today="2026-10-26")
        self.assertEqual([r["created"] for r in records], ["2026-07-01", "2026-10-26"])

    def test_reimport_has_same_ids(self):
        path = os.path.join(FIXTURES, "import_rows.jsonl")
        a, _ = sources.read_import(path, name="s", today="2026-10-26")
        b, _ = sources.read_import(path, name="s", today="2026-11-01")
        self.assertEqual([r["id"] for r in a], [r["id"] for r in b])

    def test_unknown_extension(self):
        with self.assertRaisesRegex(ValueError, "extension"):
            sources.read_import("notes.docx", name="x", today="2026-10-26")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Http(unittest.TestCase):
    def make(self, outcomes, **kw):
        self.sleeps, calls = [], []

        def opener(request, timeout):
            calls.append(request.full_url)
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return FakeResponse(json.dumps(outcome).encode())

        self.calls = calls
        return sources.Http(opener=opener, sleep=self.sleeps.append, delay=0.5, **kw)

    def http_error(self, code):
        return urllib.error.HTTPError("u", code, "x", {}, None)

    def test_retries_on_429_then_succeeds(self):
        http = self.make([self.http_error(429), self.http_error(503), {"ok": 1}])
        self.assertEqual(http.get_json("https://a.test/x"), {"ok": 1})
        self.assertEqual(len(self.calls), 3)

    def test_rate_limit_honours_retry_after(self):
        err = urllib.error.HTTPError("u", 429, "slow down", {"Retry-After": "7"}, None)
        http = self.make([err, {"ok": 1}])
        self.assertEqual(http.get_json("https://a.test/x"), {"ok": 1})
        self.assertIn(7.0, self.sleeps)

    def test_rate_limit_without_header_waits_long(self):
        http = self.make([self.http_error(429), self.http_error(429), {"ok": 1}])
        http.get_json("https://a.test/x")
        waits = sorted(self.sleeps)[-2:]
        self.assertGreaterEqual(waits[0], sources.netfetch_wait_floor())
        self.assertGreater(waits[1], waits[0])

    def test_retry_after_is_capped(self):
        err = urllib.error.HTTPError("u", 429, "slow down", {"Retry-After": "99999"}, None)
        http = self.make([err, {"ok": 1}])
        http.get_json("https://a.test/x")
        self.assertLessEqual(max(self.sleeps), 120)

    def test_gives_up_after_retries(self):
        http = self.make([self.http_error(503)] * 4, retries=3)
        with self.assertRaisesRegex(sources.FetchError, "503"):
            http.get_json("https://a.test/x")

    def test_403_fails_fast(self):
        http = self.make([self.http_error(403)])
        with self.assertRaisesRegex(sources.FetchError, "403"):
            http.get_json("https://a.test/x")
        self.assertEqual(len(self.calls), 1)

    def test_sends_user_agent(self):
        seen = []

        def opener(request, timeout):
            seen.append(request.get_header("User-agent"))
            return FakeResponse(b"{}")

        sources.Http(opener=opener, sleep=lambda s: None).get_json("https://a.test/x")
        self.assertIn("validator-skill", seen[0])

    def test_cache_serves_second_call(self):
        cache = tempfile.mkdtemp()
        http = self.make([{"n": 1}], cache_dir=cache)
        http.get_json("https://a.test/x")
        self.assertEqual(http.get_json("https://a.test/x"), {"n": 1})
        self.assertEqual(len(self.calls), 1)

    def test_retries_socket_timeout_and_incomplete_read(self):
        import http.client
        import socket
        http_ = self.make([socket.timeout("read timed out"), http.client.IncompleteRead(b"x"), {"ok": 2}])
        self.assertEqual(http_.get_json("https://a.test/x"), {"ok": 2})

    def test_empty_or_error_bodies_are_not_cached(self):
        cache = tempfile.mkdtemp()
        http_ = self.make([{"data": []}, {"error": "busy"}, {"data": [1]}, {"data": [2]}], cache_dir=cache)
        self.assertEqual(http_.get_json("https://a.test/x"), {"data": []})
        self.assertEqual(http_.get_json("https://a.test/x"), {"error": "busy"})
        self.assertEqual(http_.get_json("https://a.test/x"), {"data": [1]})
        self.assertEqual(http_.get_json("https://a.test/x"), {"data": [1]})
        self.assertEqual(len(self.calls), 3)

    def test_bad_json_is_fetch_error(self):
        def opener(request, timeout):
            return FakeResponse(b"<html>blocked</html>")

        with self.assertRaisesRegex(sources.FetchError, "JSON"):
            sources.Http(opener=opener, sleep=lambda s: None).get_json("https://a.test/x")


class Cli(unittest.TestCase):
    def test_partial_failure_exit_code(self):
        folder = tempfile.mkdtemp()
        original = sources.Http

        class Down(original):
            def get_json(self, url):
                return {"feed": {}}

        sources.Http = Down
        try:
            code = sources.main(["--dir", folder, "appstore", "--app", "1"])
        finally:
            sources.Http = original
        self.assertEqual(code, 2)

    def test_corrupt_store_is_a_clean_error(self):
        folder = tempfile.mkdtemp()
        with open(os.path.join(folder, "complaints.jsonl"), "w") as fh:
            fh.write("{broken\n")
        code = sources.main(["--dir", folder, "import", os.path.join(FIXTURES, "import_posts.txt"), "--name", "x"])
        self.assertEqual(code, 1)

    def test_report_survives_a_broken_log_line(self):
        folder = tempfile.mkdtemp()
        sources.main(["--dir", folder, "import", os.path.join(FIXTURES, "import_posts.txt"), "--name", "x"])
        with open(os.path.join(folder, "mine_log.jsonl"), "a") as fh:
            fh.write('{"at": "2026-10-2')
        self.assertEqual(sources.main(["--dir", folder, "report"]), 0)

    def test_appstore_is_never_cached(self):
        folder = tempfile.mkdtemp()
        made = []
        original = sources.Http

        class Spy(original):
            def __init__(self, **kw):
                made.append(kw.get("cache_dir"))
                super().__init__(**kw)

            def get_json(self, url):
                return {"feed": {}}

        sources.Http = Spy
        try:
            sources.main(["--dir", folder, "appstore", "--app", "1"])
        finally:
            sources.Http = original
        self.assertEqual(made[-1], None)


    def test_import_writes_store_log_and_report(self):
        folder = tempfile.mkdtemp()
        code = sources.main(["--dir", folder, "import", os.path.join(FIXTURES, "import_posts.txt"), "--name", "x"])
        self.assertEqual(code, 0)
        self.assertEqual(len(store.load(os.path.join(folder, "complaints.jsonl"))), 2)
        with open(os.path.join(folder, "mine_log.jsonl")) as fh:
            log = [json.loads(line) for line in fh]
        self.assertEqual((log[0]["source"], log[0]["added"]), ("import", 2))
        self.assertEqual(sources.main(["--dir", folder, "report"]), 0)
        with open(os.path.join(folder, "sources.md")) as fh:
            report = fh.read()
        self.assertIn("| import |", report)
        self.assertIn("2 complaints", report)


if __name__ == "__main__":
    unittest.main()
