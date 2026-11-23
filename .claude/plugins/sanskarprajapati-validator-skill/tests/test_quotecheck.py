import contextlib
import io
import os
import unittest

from _load import load
from verdict_world import make, write_json

quotecheck = load("validate-verdict", "quotecheck")


def write(folder, name, text):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        fh.write(text)


class Check(unittest.TestCase):
    def setUp(self):
        self.folder, self.posts = make()
        self.r1 = self.posts["r1"]

    def test_good_quote_with_link_passes(self):
        write(self.folder, "a.md", '> "it still drops my WhatsApp every single week" [%s](%s)\n' % (self.r1["id"], self.r1["url"]))
        result = quotecheck.check_folder(self.folder)
        self.assertEqual((result["ok"], result["failed"]), (1, []))

    def test_changed_words_fail_with_file_and_line(self):
        write(self.folder, "a.md", 'intro\n> "it always drops my WhatsApp every week" [%s](x)\n' % self.r1["id"])
        failed = quotecheck.check_folder(self.folder)["failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual((failed[0]["file"], failed[0]["line"], failed[0]["id"]), ("a.md", 2, self.r1["id"]))

    def test_unknown_id_fails(self):
        write(self.folder, "a.md", "as R0000beef says\n")
        self.assertEqual(quotecheck.check_folder(self.folder)["unknown"][0]["id"], "R0000beef")

    def test_markdown_escapes_are_undone_before_checking(self):
        record = self.posts["r3"]
        write(self.folder, "a.md", '"I keep missing LinkedIn replies" %s\n' % record["id"])
        write(self.folder, "b.md", '"I\\\'m paying $40/mo and it still drops" %s\n' % self.r1["id"])
        self.assertEqual(quotecheck.check_folder(self.folder)["failed"], [])

    def test_hidden_contact_details_are_gaps(self):
        folder, _ = make()
        from verdict_world import store
        r = store.build_record(source="reddit", native_id="pii", url="https://reddit.com/pii",
                               text="I keep missing replies, mail me at gil@example.com or call", created="2026-10-01")
        path = os.path.join(folder, "complaints.jsonl")
        store.save(path, store.load(path) + [r])
        write(folder, "a.md", '"I keep missing replies, mail me at (email hidden) or call" %s\n' % r["id"])
        self.assertEqual(quotecheck.check_folder(folder)["failed"], [])

    def test_ids_in_competitor_stores_count(self):
        from verdict_world import store
        comp = os.path.join(self.folder, "competitors", "beeper")
        r = store.build_record(source="appstore", native_id="c1", url="https://apps.apple.com/x",
                               text="The app logs me out every single day now", created="2026-10-01")
        store.save(os.path.join(comp, "complaints.jsonl"), [r])
        write(self.folder, "gaps.md", '> "logs me out every single day" %s\n' % r["id"])
        self.assertEqual(quotecheck.check_folder(self.folder)["ok"], 1)

    def test_uncited_quotes_are_counted_not_failed(self):
        write(self.folder, "interview.md", 'Ask: "Tell me about the last time this happened."\n')
        result = quotecheck.check_folder(self.folder)
        self.assertEqual((result["failed"], result["uncited"]), ([], 1))

    def test_cluster_work_files_are_skipped(self):
        os.makedirs(os.path.join(self.folder, "cluster", "briefs"))
        write(os.path.join(self.folder, "cluster", "briefs"), "b001.md", '"made up words here" R0000beef\n')
        self.assertEqual(quotecheck.check_folder(self.folder)["unknown"], [])

    def test_trial_work_files_are_skipped(self):
        os.makedirs(os.path.join(self.folder, "trial", "briefs"))
        write(os.path.join(self.folder, "trial", "briefs"), "defense.md", 'like R1a2b3c4d, an example id\n')
        self.assertEqual(quotecheck.check_folder(self.folder)["unknown"], [])

    def test_other_quote_marks_are_checked(self):
        for text in ("He said \u2018we pay fifty bucks a month\u2019 %s\n", "\u00abwe pay fifty bucks a month\u00bb %s\n"):
            write(self.folder, "a.md", text % self.r1["id"])
            self.assertEqual(len(quotecheck.check_folder(self.folder)["failed"]), 1, text)

    def test_hidden_marker_cannot_bridge_a_paragraph(self):
        text = "I would never ever recommend this to anyone because it is slow and buggy and costs a lot ok"
        self.assertFalse(quotecheck.quote_matches("I would (email hidden) ok", text))
        self.assertTrue(quotecheck.quote_matches("mail me at (email hidden) or call",
                                                 "please mail me at gil@example.com or call later"))
        self.assertFalse(quotecheck.quote_matches("ail me at (email hidden) or call",
                                                  "please mail me at gil@example.com or call later"))

    def test_html_entities_in_posts_are_not_unescaped_twice(self):
        from verdict_world import store
        r = store.build_record(source="reddit", native_id="amp", url="https://reddit.com/amp",
                               text="they wrote a &amp;amp; b in the docs", created="2026-10-01")
        path = os.path.join(self.folder, "complaints.jsonl")
        store.save(path, store.load(path) + [r])
        write(self.folder, "a.md", '"wrote a &amp; b in the docs" %s\n' % r["id"])
        self.assertEqual(quotecheck.check_folder(self.folder)["failed"], [])

    def test_strict_files_fail_on_uncited_quotes(self):
        write(self.folder, "report.md", 'R0000beef aside, "I would happily pay $500 a month" said nobody\n')
        result = quotecheck.check_folder(self.folder, strict=("report.md",))
        self.assertTrue(result["failed"])

    def test_cli_exit_codes(self):
        write(self.folder, "a.md", '"it still drops my WhatsApp every single week" %s\n' % self.r1["id"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(quotecheck.main(["--dir", self.folder]), 0)
        write(self.folder, "b.md", '"words nobody ever wrote" %s\n' % self.r1["id"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(quotecheck.main(["--dir", self.folder]), 1)


if __name__ == "__main__":
    unittest.main()
