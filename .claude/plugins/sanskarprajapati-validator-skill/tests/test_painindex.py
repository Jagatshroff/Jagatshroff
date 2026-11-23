import contextlib
import io
import json
import os
import tempfile
import unittest

from _load import load

painindex = load("validate-pain", "painindex")
store = load("validate-mine", "store")

TODAY = "2026-10-26"
THEMES = [{"key": "money-pain", "name": "Costs real money", "definition": "d"},
          {"key": "mild", "name": "Mild annoyance", "definition": "d"},
          {"key": "rare", "name": "Rare", "definition": "d"}]


class World:
    """Builds a validator/ folder with complaints, labels, themes and an idea."""

    def __init__(self):
        self.dir = tempfile.mkdtemp()
        self.records, self.labels = [], []

    def add(self, theme, text, quote, created="2026-10-01", author=None, intensity=2, complaint=True, community="c1"):
        n = len(self.records) + 1
        r = store.build_record(source="reddit", native_id="x%d" % n, url="https://reddit.com/%d" % n, text=text,
                               created=created, author=author if author is not None else "u%d" % n,
                               community=community, score=n)
        self.records.append(r)
        self.labels.append({"id": r["id"], "relevant": complaint, "complaint": complaint, "theme": theme if complaint else "",
                            "new_theme": "", "who": "", "tried": [], "intensity": intensity if complaint else 0,
                            "quote": quote if complaint else ""})
        return r

    def save(self, bar=None):
        store.save(os.path.join(self.dir, "complaints.jsonl"), self.records)
        store.save(os.path.join(self.dir, "labels.jsonl"), self.labels)
        with open(os.path.join(self.dir, "themes.json"), "w") as fh:
            json.dump({"codebook": THEMES, "themes": [], "other": [], "totals": {}}, fh)
        if bar is not False:
            with open(os.path.join(self.dir, "idea.json"), "w") as fh:
                json.dump({"bar": bar or {"evidence": {"min_complaints": 20, "min_money_signals": 5, "max_age_months": 24},
                                          "real_world": ["x"]}}, fh)
        return self.dir


def standard_world():
    w = World()
    for n in range(14):
        w.add("money-pain", "I'm paying $40/mo and it still drops chats, I hate it. I'd pay double for one that works.",
              "I'd pay double for one that works", community="c%d" % (n % 6), intensity=3)
    for n in range(12):
        w.add("mild", "It would be nice if the icons were bigger, kind of annoying", "kind of annoying", intensity=1,
              author="same")
    for n in range(3):
        w.add("rare", "I keep a spreadsheet of who I owe replies to", "I keep a spreadsheet")
    w.add("money-pain", "Way too expensive for what it does", "Way too expensive", created="2023-01-01")  # too old
    w.add("", "Launching my new app today!", "", complaint=False)
    return w


class Scoring(unittest.TestCase):
    def setUp(self):
        self.result = painindex.build(standard_world().save(), today=TODAY)
        self.by_key = {t["key"]: t for t in self.result["themes"]}

    def test_money_theme_ranks_first_and_is_worth_money(self):
        self.assertEqual(self.result["themes"][0]["key"], "money-pain")
        self.assertEqual(self.by_key["money-pain"]["tier"], "worth money")

    def test_mild_single_author_theme_is_noise(self):
        mild = self.by_key["mild"]
        self.assertEqual(mild["tier"], "noise")
        self.assertLess(mild["components"]["breadth"], 0.6)

    def test_small_theme_is_too_few_to_call(self):
        self.assertEqual(self.by_key["rare"]["tier"], "too few to call")
        self.assertEqual(self.by_key["rare"]["metrics"]["workaround"], 3)

    def test_old_complaints_are_left_out(self):
        self.assertEqual(self.by_key["money-pain"]["metrics"]["complaints"], 14)
        self.assertEqual(self.result["totals"]["too_old"], 1)
        self.assertEqual(self.result["totals"]["in_window"], 29)

    def test_score_is_weighted_sum(self):
        t = self.by_key["money-pain"]
        expected = round(sum(painindex.WEIGHTS[k] * v for k, v in t["components"].items()))
        self.assertEqual(t["score"], expected)
        self.assertTrue(all(0 <= v <= 1 for v in t["components"].values()))
        self.assertEqual(sum(painindex.WEIGHTS.values()), 100)

    def test_examples_are_verbatim_and_linked(self):
        for example in self.by_key["money-pain"]["examples"]:
            record = [r for r in store.load(os.path.join(self.result["dir"], "complaints.jsonl")) if r["id"] == example["id"]][0]
            self.assertTrue(store.verbatim(example["quote"], record["text"]))
            self.assertEqual(example["url"], record["url"])
        self.assertLessEqual(len(self.by_key["money-pain"]["examples"]), 3)

    def test_bar(self):
        bar = self.result["bar"]
        self.assertEqual(bar["complaints"], {"need": 20, "have": 29, "pass": True})
        self.assertEqual(bar["money_signals"], {"need": 5, "have": 14, "pass": True})


class Rules(unittest.TestCase):
    def test_no_money_means_never_worth_money(self):
        w = World()
        for n in range(30):
            w.add("mild", "This is an absolute nightmare, I keep it all in a spreadsheet and hate it",
                  "absolute nightmare", intensity=3, community="c%d" % n)
        theme = [t for t in painindex.build(w.save(), today=TODAY)["themes"] if t["key"] == "mild"][0]
        self.assertGreaterEqual(theme["score"], 50)
        self.assertNotEqual(theme["tier"], "worth money")

    def test_forged_quote_is_dropped_from_examples(self):
        w = World()
        for n in range(12):
            w.add("mild", "real words here about the pain of it all", "words nobody wrote")
        theme = [t for t in painindex.build(w.save(), today=TODAY)["themes"] if t["key"] == "mild"][0]
        self.assertEqual(theme["examples"], [])

    def test_deterministic(self):
        d = standard_world().save()
        a = painindex.build(d, today=TODAY)
        b = painindex.build(d, today=TODAY)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_without_idea_uses_defaults(self):
        result = painindex.build(standard_world().save(bar=False), today=TODAY)
        self.assertEqual(result["bar"]["complaints"]["need"], painindex.DEFAULT_BAR["min_complaints"])

    def test_missing_labels_is_a_clear_error(self):
        w = standard_world()
        w.save()
        os.remove(os.path.join(w.dir, "labels.jsonl"))
        with self.assertRaisesRegex(ValueError, "validate-cluster"):
            painindex.build(w.dir, today=TODAY)


class Output(unittest.TestCase):
    def test_cli_writes_files(self):
        d = standard_world().save()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(painindex.main(["--dir", d, "--today", TODAY]), 0)
        with open(os.path.join(d, "pain.md")) as fh:
            md = fh.read()
        self.assertIn("| 1 | Costs real money |", md)
        self.assertIn("worth money", md)
        self.assertIn("How the score works", md)
        self.assertIn("in 1 community.", md)
        self.assertIn("in 6 communities.", md)
        self.assertRegex(md, r'> "I\'d pay double for one that works" \[R[0-9a-f]{8}\]\(https://')
        with open(os.path.join(d, "pain.json")) as fh:
            self.assertEqual(json.load(fh)["themes"][0]["key"], "money-pain")
        with open(os.path.join(d, "signals.jsonl")) as fh:
            rows = [json.loads(line) for line in fh]
        self.assertEqual(len(rows), 29)
        self.assertIn("wtp", rows[0]["signals"])

    def test_report_escapes_hostile_text(self):
        w = World()
        for n in range(12):
            w.add("mild", "evil [click](javascript:alert(1)) <b>x</b> and more words here", "evil [click](javascript:alert(1)) <b>x</b>")
        w.records[0]["url"] = "javascript:alert(1)"
        d = w.save()
        with contextlib.redirect_stdout(io.StringIO()):
            painindex.main(["--dir", d, "--today", TODAY])
        with open(os.path.join(d, "pain.md")) as fh:
            md = fh.read()
        self.assertNotIn("](javascript:", md)
        self.assertNotIn("<b>", md)

    def test_bare_links_do_not_autolink(self):
        mdsafe = load("validate-mine", "mdsafe")
        out = mdsafe.md("go to www.evil.example or http://evil.example now")
        self.assertNotIn("www.evil", out)
        self.assertNotIn("http://", out)

    def test_partial_labelling_is_shown(self):
        w = standard_world()
        d = w.save()
        with open(os.path.join(d, "themes.json"), "w") as fh:
            json.dump({"codebook": THEMES, "themes": [], "other": [],
                       "totals": {"in_store": 300, "labeled": 31, "unlabeled": 269}}, fh)
        with contextlib.redirect_stdout(io.StringIO()):
            painindex.main(["--dir", d, "--today", TODAY])
        with open(os.path.join(d, "pain.md")) as fh:
            self.assertIn("269 of 300 mined posts are not labelled yet", fh.read())

    def test_bad_label_values_are_a_clean_error(self):
        w = standard_world()
        w.labels[0]["intensity"] = None
        d = w.save()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(painindex.main(["--dir", d, "--today", TODAY]), 1)

    def test_one_other_is_singular(self):
        w = standard_world()
        w.labels[0]["theme"] = "other"
        d = w.save()
        with contextlib.redirect_stdout(io.StringIO()):
            painindex.main(["--dir", d, "--today", TODAY])
        with open(os.path.join(d, "pain.md")) as fh:
            self.assertIn("1 complaint is still labelled `other`", fh.read())

    def test_bad_today(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(painindex.main(["--dir", tempfile.mkdtemp(), "--today", "soon"]), 1)


if __name__ == "__main__":
    unittest.main()
