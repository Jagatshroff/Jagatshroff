import json
import os
import tempfile
import unittest

from _load import load

store = load("validate-mine", "store")


def rec(native="a1", text="I hate switching between five apps to answer messages every day", **extra):
    fields = dict(source="reddit", native_id=native, url="https://reddit.com/x/" + native, text=text,
                  created="2026-10-01")
    fields.update(extra)
    return store.build_record(**fields)


class CleanText(unittest.TestCase):
    def test_strips_html_and_entities(self):
        raw = "I can&#x27;t stand it.<p>Second &amp; last <a href=\"x\">link</a>"
        self.assertEqual(store.clean_text(raw), "I can't stand it.\nSecond & last link")

    def test_collapses_whitespace(self):
        self.assertEqual(store.clean_text("  a \t b\n\n\n c  "), "a b\n\nc")

    def test_none_is_empty(self):
        self.assertEqual(store.clean_text(None), "")


class Verbatim(unittest.TestCase):
    TEXT = "I hate   switching apps.\nIt's a nightmare, honestly."

    def test_exact_substring(self):
        self.assertTrue(store.verbatim("switching apps. It's a nightmare", self.TEXT))

    def test_whitespace_differences_are_fine(self):
        self.assertTrue(store.verbatim("I hate switching apps.", self.TEXT))

    def test_curly_quotes_match_straight(self):
        self.assertTrue(store.verbatim("It\u2019s a nightmare", self.TEXT))

    def test_changed_words_fail(self):
        self.assertFalse(store.verbatim("I hate switching between apps", self.TEXT))
        self.assertFalse(store.verbatim("it's a nightmare", self.TEXT))  # case matters: quotes are exact

    def test_empty_quote_fails(self):
        self.assertFalse(store.verbatim("  ", self.TEXT))

    def test_too_short_to_be_evidence(self):
        self.assertFalse(store.verbatim("nightmare", self.TEXT))
        self.assertFalse(store.verbatim("a nightmare", self.TEXT))

    def test_must_start_and_end_on_word_edges(self):
        text = "Paying this bill every month is killing me"
        self.assertTrue(store.verbatim("this bill every month", text))
        self.assertFalse(store.verbatim("ill every month", text))
        self.assertFalse(store.verbatim("this bill every mon", text))

    def test_later_occurrence_can_satisfy_edges(self):
        self.assertTrue(store.verbatim("is very slow", "Thisis very slow. It is very slow."))


class Ids(unittest.TestCase):
    def test_stable_and_prefixed(self):
        a = store.make_id("reddit", "abc")
        self.assertEqual(a, store.make_id("reddit", "abc"))
        self.assertRegex(a, r"^R[0-9a-f]{8}$")
        self.assertTrue(store.make_id("hn", "1").startswith("H"))
        self.assertTrue(store.make_id("appstore", "1").startswith("A"))
        self.assertTrue(store.make_id("import", "1").startswith("I"))

    def test_source_changes_id(self):
        self.assertNotEqual(store.make_id("reddit", "1")[1:], store.make_id("hn", "1")[1:])

    def test_unknown_source(self):
        with self.assertRaises(ValueError):
            store.make_id("myspace", "1")


class BuildRecord(unittest.TestCase):
    def test_fills_defaults(self):
        r = rec()
        self.assertEqual(r["id"], store.make_id("reddit", "a1"))
        self.assertEqual(r["author"], "")
        self.assertIsNone(r["score"])
        self.assertIsNone(r["rating"])

    def test_missing_required(self):
        with self.assertRaisesRegex(ValueError, "url"):
            store.build_record(source="hn", native_id="1", url="", text="some text here", created="2026-01-01")

    def test_bad_date(self):
        with self.assertRaisesRegex(ValueError, "created"):
            rec(created="yesterday")
        with self.assertRaisesRegex(ValueError, "created"):
            rec(created="2024-13-45")

    def test_control_characters_are_stripped(self):
        self.assertEqual(store.clean_text("bad\x1b[31m red\x07 text\x9b"), "bad[31m red text")

    def test_accepts_full_timestamp(self):
        self.assertEqual(rec(created="2026-10-23T10:39:07-07:00")["created"], "2026-10-23")

    def test_text_is_cleaned_and_capped(self):
        r = rec(text="<p>" + "word " * 2000)
        self.assertLessEqual(len(r["text"]), store.MAX_TEXT)
        self.assertTrue(r["truncated"])
        self.assertFalse(rec()["truncated"])

    def test_unknown_field_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            rec(colour="red")

    def test_score_must_be_int(self):
        self.assertEqual(rec(score="12")["score"], 12)
        with self.assertRaises(ValueError):
            rec(score="lots")


class Merge(unittest.TestCase):
    def test_adds_new_and_skips_same_id(self):
        merged, added, dupes = store.merge([rec("a")], [rec("a"), rec("b", text="totally different words over here ok")])
        self.assertEqual([r["native_id"] for r in merged], ["a", "b"])
        self.assertEqual((added, dupes), (1, 1))

    def test_skips_near_duplicate_text(self):
        text = "Beeper keeps disconnecting my Instagram account every few days and I am tired of it"
        merged, added, dupes = store.merge([rec("a", text=text)], [rec("b", text=text + "!!")])
        self.assertEqual((len(merged), added, dupes), (1, 0, 1))

    def test_keeps_different_texts(self):
        merged, _, _ = store.merge([], [rec("a", text="one two three four five six seven"),
                                        rec("b", text="eight nine ten eleven twelve thirteen")])
        self.assertEqual(len(merged), 2)

    def test_does_not_mutate_inputs(self):
        existing = [rec("a")]
        before = json.dumps(existing)
        store.merge(existing, [rec("b", text="something else entirely different here")])
        self.assertEqual(json.dumps(existing), before)

    def test_short_texts_dedupe_only_for_same_author(self):
        merged, _, dupes = store.merge([], [rec("a", text="so bad", author="x"), rec("b", text="So bad.", author="x"),
                                            rec("c", text="so good", author="x")])
        self.assertEqual((len(merged), dupes), (2, 1))

    def test_short_texts_from_different_people_are_kept(self):
        merged, _, _ = store.merge([], [rec("a", text="Too expensive.", author="ann"),
                                        rec("b", text="Too expensive.", author="bob"),
                                        rec("c", text="Too expensive.")])
        self.assertEqual(len(merged), 3)

    def test_non_latin_texts_are_not_merged(self):
        merged, _, _ = store.merge([], [rec("a", text="这个应用每天都崩溃，我受不了了", author="u1"),
                                        rec("b", text="客服从来不回复我的消息", author="u2"),
                                        rec("c", text="😡😡😡", author="u3"),
                                        rec("d", text="😭", author="u4")])
        self.assertEqual(len(merged), 4)

    def test_non_latin_near_duplicates_still_merge(self):
        text = "Приложение постоянно отключает мой WhatsApp и я больше не могу это терпеть каждый день"
        merged, _, dupes = store.merge([], [rec("a", text=text), rec("b", text=text + "!!")])
        self.assertEqual((len(merged), dupes), (1, 1))

    def test_accents_are_kept(self):
        self.assertNotEqual(store._normal("café crème"), store._normal("caf cr me"))


class Files(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "complaints.jsonl")

    def test_add_round_trip(self):
        self.assertEqual(store.add(self.path, [rec("a")]), (1, 0))
        self.assertEqual(store.add(self.path, [rec("a"), rec("b", text="a fresh complaint with new words")]), (1, 1))
        self.assertEqual([r["native_id"] for r in store.load(self.path)], ["a", "b"])

    def test_load_missing_is_empty(self):
        self.assertEqual(store.load(self.path), [])

    def test_load_reports_bad_line(self):
        with open(self.path, "w") as fh:
            fh.write(json.dumps(rec()) + "\n{not json\n")
        with self.assertRaisesRegex(ValueError, "line 2"):
            store.load(self.path)

    def test_save_leaves_no_temp_files(self):
        store.save(self.path, [rec()])
        self.assertEqual(os.listdir(self.dir), ["complaints.jsonl"])

    def test_saved_file_is_readable_by_others(self):
        store.save(self.path, [rec()])
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o644)

    def test_stats(self):
        store.save(self.path, [rec("a", created="2025-01-02"),
                               rec("b", text="another one with other words", created="2026-03-04"),
                               store.build_record(source="hn", native_id="9", url="https://news.ycombinator.com/item?id=9",
                                                  text="hn complaint text goes here", created="2026-05-06")])
        s = store.stats(store.load(self.path))
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["by_source"], {"hn": 1, "reddit": 2})
        self.assertEqual((s["first"], s["last"]), ("2025-01-02", "2026-05-06"))


if __name__ == "__main__":
    unittest.main()
