import contextlib
import io
import json
import os
import tempfile
import unittest

from _load import load

gapmap = load("validate-competitors", "gapmap")
store = load("validate-mine", "store")

CODEBOOK = {"themes": [{"key": k, "name": k.title(), "definition": "d"} for k in ("drops", "price", "triage", "noise")]}


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(data, fh)


def competitor(root, slug, counts, other=(), codebook=CODEBOOK):
    folder = os.path.join(root, "competitors", slug)
    records, labels = [], []
    for theme, n in counts.items():
        for i in range(n):
            text = "%s review number %d says the %s problem keeps happening to me" % (slug, i, theme)
            r = store.build_record(source="appstore", native_id="%s-%s-%d" % (slug, theme, i), text=text,
                                   url="https://apps.apple.com/us/app/id1?see-all=reviews", created="2026-10-01",
                                   community=slug)
            records.append(r)
            labels.append({"id": r["id"], "relevant": True, "complaint": True, "theme": theme, "new_theme": "",
                           "who": "", "tried": [], "intensity": 2, "quote": "the %s problem keeps happening" % theme})
    store.save(os.path.join(folder, "complaints.jsonl"), records)
    store.save(os.path.join(folder, "labels.jsonl"), labels)
    write_json(os.path.join(folder, "cluster_codebook.json"), codebook)
    total = sum(counts.values()) + len(other)
    write_json(os.path.join(folder, "themes.json"), {
        "totals": {"complaints": total},
        "themes": [{"key": k, "count": n} for k, n in counts.items()],
        "other": [{"id": "x%d" % i, "new_theme": t} for i, t in enumerate(other)]})


def world():
    root = tempfile.mkdtemp()
    write_json(os.path.join(root, "cluster_codebook.json"), CODEBOOK)
    write_json(os.path.join(root, "pain.json"), {"themes": [
        {"key": "drops", "name": "Drops", "score": 72, "tier": "worth money"},
        {"key": "triage", "name": "Triage", "score": 55, "tier": "real, unproven"},
        {"key": "noise", "name": "Noise", "score": 20, "tier": "noise"},
        {"key": "price", "name": "Price", "score": 45, "tier": "real, unproven"}]})
    competitor(root, "beeper", {"drops": 30, "price": 10, "noise": 6, "triage": 0},
               other=["no email support", "No email support", "battery drain"])
    competitor(root, "texts", {"drops": 2, "price": 25, "noise": 1, "triage": 0})
    return root


class Build(unittest.TestCase):
    def setUp(self):
        self.result = gapmap.build(world())
        self.rows = {r["key"]: r for r in self.result["themes"]}

    def test_shares(self):
        self.assertAlmostEqual(self.rows["drops"]["shares"]["beeper"], 30 / 49, places=3)
        self.assertEqual(self.rows["triage"]["shares"], {"beeper": 0.0, "texts": 0.0})

    def test_status(self):
        self.assertEqual(self.rows["drops"]["status"], "open gap")
        self.assertEqual(self.rows["price"]["status"], "open gap")
        self.assertEqual(self.rows["noise"]["status"], "they struggle too")
        self.assertEqual(self.rows["triage"]["status"], "maybe solved")

    def test_open_gaps_rank_first_by_pain(self):
        self.assertEqual([r["key"] for r in self.result["themes"]][:2], ["drops", "price"])

    def test_other_names_are_counted(self):
        self.assertEqual(self.result["competitors"]["beeper"]["other"], {"no email support": 2, "battery drain": 1})

    def test_examples_are_verbatim(self):
        examples = self.rows["drops"]["examples"]["beeper"]
        self.assertTrue(examples)
        self.assertLessEqual(len(examples), 2)
        self.assertIn("keeps happening", examples[0]["quote"])

    def test_thin_competitor_makes_silence_unclear(self):
        root = world()
        competitor(root, "tiny", {"drops": 3, "price": 0, "noise": 0, "triage": 0})
        rows = {r["key"]: r for r in gapmap.build(root)["themes"]}
        self.assertEqual(rows["triage"]["status"], "unclear")
        self.assertTrue(gapmap.build(root)["competitors"]["tiny"]["thin"])


class Edges(unittest.TestCase):
    def test_thin_competitor_cannot_make_an_open_gap(self):
        root = world()
        competitor(root, "tiny", {"triage": 2, "drops": 1})
        rows = {r["key"]: r for r in gapmap.build(root)["themes"]}
        self.assertEqual(rows["triage"]["status"], "unclear")

    def test_without_pain_json_nothing_is_struggling(self):
        root = world()
        os.remove(os.path.join(root, "pain.json"))
        statuses = {r["key"]: r["status"] for r in gapmap.build(root)["themes"]}
        self.assertNotIn("they struggle too", statuses.values())
        with contextlib.redirect_stdout(io.StringIO()):
            gapmap.main(["--dir", root])
        with open(os.path.join(root, "gaps.md")) as fh:
            self.assertNotIn("None", fh.read())

    def test_hidden_folders_are_skipped(self):
        root = world()
        os.makedirs(os.path.join(root, "competitors", ".cache"))
        os.makedirs(os.path.join(root, "competitors", "__pycache__"))
        self.assertEqual(sorted(gapmap.build(root)["competitors"]), ["beeper", "texts"])

    def test_odd_other_entries_do_not_crash(self):
        root = world()
        path = os.path.join(root, "competitors", "texts", "themes.json")
        with open(path) as fh:
            data = json.load(fh)
        data["other"] = ["x", None, {"new_theme": 5}]
        write_json(path, data)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertIn(gapmap.main(["--dir", root]), (0, 1))


class Errors(unittest.TestCase):
    def test_codebook_mismatch(self):
        root = world()
        competitor(root, "odd", {"drops": 20}, codebook={"themes": [{"key": "drops", "name": "x", "definition": "y"}]})
        with self.assertRaisesRegex(ValueError, "odd"):
            gapmap.build(root)

    def test_no_competitors(self):
        root = tempfile.mkdtemp()
        write_json(os.path.join(root, "cluster_codebook.json"), CODEBOOK)
        with self.assertRaisesRegex(ValueError, "no competitor"):
            gapmap.build(root)

    def test_unlabelled_competitor_is_named(self):
        root = world()
        os.makedirs(os.path.join(root, "competitors", "halfway"))
        with self.assertRaisesRegex(ValueError, "halfway"):
            gapmap.build(root)


class Cli(unittest.TestCase):
    def test_writes_files(self):
        root = world()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gapmap.main(["--dir", root]), 0)
        with open(os.path.join(root, "gaps.md")) as fh:
            md = fh.read()
        self.assertIn("| Drops | 72 worth money | 61% | 7% | open gap |", md)  # 30/49 and 2/28
        self.assertIn("no email support (2)", md)
        with open(os.path.join(root, "gaps.json")) as fh:
            self.assertEqual(json.load(fh)["themes"][0]["key"], "drops")


if __name__ == "__main__":
    unittest.main()
