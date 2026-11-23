import json
import os
import re
import unittest

from _load import load
from verdict_world import store, write_json
from test_report import build, finished
from test_trial import ruling, run

report = load("validate-verdict", "report")


def read(folder, name):
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def with_extra_posts(folder):
    """A relevant post that is not a complaint, a noise post, and one competitor complaint."""
    path = os.path.join(folder, "complaints.jsonl")
    records, labels = store.load(path), store.load(os.path.join(folder, "labels.jsonl"))
    extra = [("launch1", "Launching my unified inbox app today, come try it", True),
             ("noise1", "My calendar app is fine but my inbox at work is a mess", False)]
    for native, text, relevant in extra:
        r = store.build_record(source="reddit", native_id=native, url="https://www.reddit.com/r/x/%s/" % native,
                               text=text, created="2026-10-02", author="u_" + native, community="startups")
        records.append(r)
        labels.append({"id": r["id"], "relevant": relevant, "complaint": False, "theme": "", "new_theme": "",
                       "who": "", "tried": [], "intensity": 0, "quote": ""})
    store.save(path, records)
    store.save(os.path.join(folder, "labels.jsonl"), labels)
    comp = os.path.join(folder, "competitors", "beeper")
    c = store.build_record(source="appstore", native_id="c1", url="https://apps.apple.com/us/app/id1?see-all=reviews",
                           text="It keeps logging me out of WhatsApp every single day", created="2026-10-03",
                           author="Reviewer", community="Beeper")
    store.save(os.path.join(comp, "complaints.jsonl"), [c])
    store.save(os.path.join(comp, "labels.jsonl"), [{"id": c["id"], "relevant": True, "complaint": True,
                                                     "theme": "drops", "new_theme": "", "who": "", "tried": [],
                                                     "intensity": 2, "quote": "keeps logging me out of WhatsApp"}])
    return folder, records


class Html(unittest.TestCase):
    def setUp(self):
        self.folder = finished()
        code, _, log = build(self.folder)
        self.assertEqual(code, 0, log)
        self.html = read(self.folder, "report.html")

    def test_written_with_the_verdict(self):
        self.assertIsNotNone(self.html)
        self.assertTrue(self.html.lower().startswith("<!doctype html>"))
        self.assertIn("a 200-signup waitlist for recruiters", self.html)
        self.assertRegex(self.html, r'class="ruling"[^>]*>\s*test\s*<')

    def test_self_contained(self):
        self.assertIsNone(re.search(r"<(script|link|img|iframe)\b", self.html, re.I), "no external or scripted resources")

    def test_theme_aware(self):
        self.assertIn("prefers-color-scheme: dark", self.html)

    def test_verified_quote_with_its_link(self):
        self.assertIn("it still drops my WhatsApp every single week", self.html)
        self.assertIn('href="https://www.reddit.com/r/x/r1/"', self.html)

    def test_bar_and_pain_are_there(self):
        self.assertIn("Connections drop", self.html)
        self.assertIn("worth money", self.html)
        self.assertIn("200 waitlist signups from strangers", self.html)

    def test_no_author_handles(self):
        self.assertNotIn("u_r1", self.html)


class Bars(unittest.TestCase):
    def test_inner_bar_is_clamped(self):
        reporthtml = load("validate-verdict", "reporthtml")
        out = reporthtml._bars([{"a": 10, "b": 50}], lambda r: "x", lambda r: r["a"], inner=lambda r: r["b"])
        self.assertNotIn("500.0%", out)


class Hostile(unittest.TestCase):
    def test_judge_text_is_escaped(self):
        folder = finished()
        run(folder, "judge")
        ruling(folder, {"ruling": "test", "narrow_to": "", "next_test": "<img src=x onerror=alert(1)>",
                        "reasons": [{"text": "<script>alert(1)</script> real", "cites": ["D1"]}]})
        code, _, log = build(folder)
        self.assertEqual(code, 0, log)
        html = read(folder, "report.html")
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;img src=x", html)

    def test_a_tampered_quote_removes_every_output(self):
        folder = finished()
        path = os.path.join(folder, "verdict.json")
        with open(path) as fh:
            verdict = json.load(fh)
        verdict["reasons"][0]["claims"][0]["quote"] = "it drops everything and I hate it"
        write_json(path, verdict)
        code, _, _ = build(folder)
        self.assertEqual(code, 1)
        for name in ("report.md", "report.html", "links.md"):
            self.assertIsNone(read(folder, name), name)


class Links(unittest.TestCase):
    def setUp(self):
        folder = finished()
        self.folder, self.records = with_extra_posts(folder)
        code, _, log = build(self.folder)
        self.assertEqual(code, 0, log)
        self.links = read(self.folder, "links.md")

    def test_every_mined_link_appears_once(self):
        for r in self.records:
            self.assertEqual(self.links.count("(%s)" % r["url"]), 1, r["url"])

    def test_grouped_by_theme_then_the_rest(self):
        order = [self.links.index(h) for h in ("## Connections drop", "## Missed replies",
                                               "## Relevant, not complaints", "## Not relevant",
                                               "## Competitor: beeper")]
        self.assertEqual(order, sorted(order))

    def test_complaints_carry_their_verified_quote(self):
        section = self.links.split("## Connections drop")[1].split("## ")[0]
        self.assertIn('"it still drops my WhatsApp every single week"', section)

    def test_hostile_theme_names_are_escaped(self):
        folder = finished()
        path = os.path.join(folder, "pain.json")
        with open(path) as fh:
            pain = json.load(fh)
        pain["themes"][0]["name"] = "Pricing\n\n[Claim your prize](https://evil.example) <b>x</b>"
        write_json(path, pain)
        code, _, log = build(folder)
        self.assertEqual(code, 0, log)
        links = read(folder, "links.md")
        self.assertNotIn("](https://evil.example)", links)
        self.assertNotIn("<b>", links)
        self.assertNotIn("\n\n[Claim", links)

    def test_a_renderer_crash_leaves_nothing_behind(self):
        folder = finished()
        original = report.reporthtml.render_html
        report.reporthtml.render_html = lambda *a: 1 / 0
        try:
            code, _, _ = build(folder)
        finally:
            report.reporthtml.render_html = original
        self.assertEqual(code, 1)
        for name in ("report.md", "report.html", "links.md"):
            self.assertIsNone(read(folder, name), name)

    def test_no_author_handles(self):
        for handle in ("u_r1", "u_launch1", "Reviewer"):
            self.assertNotIn(handle, self.links)


if __name__ == "__main__":
    unittest.main()
