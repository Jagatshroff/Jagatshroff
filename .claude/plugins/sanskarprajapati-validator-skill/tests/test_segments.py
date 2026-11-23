import contextlib
import io
import json
import os
import tempfile
import unittest

from _load import load

segments = load("validate-segment", "segments")
store = load("validate-mine", "store")


class Roles(unittest.TestCase):
    def test_normalise(self):
        self.assertEqual(segments.normalise_role("Recruiters"), "recruiter")
        self.assertEqual(segments.normalise_role("  a Freelance designer. "), "freelance designer")
        self.assertEqual(segments.normalise_role("an SDR"), "sdr")
        self.assertEqual(segments.normalise_role("business"), "business")
        self.assertEqual(segments.normalise_role(""), "")
        self.assertEqual(segments.normalise_role("agencies"), "agency")
        self.assertEqual(segments.normalise_role("businesses"), "business")
        self.assertEqual(segments.normalise_role("PMs"), "pm")
        self.assertEqual(segments.normalise_role("I'm a founder"), "founder")
        for empty in ("n/a", "unknown", "None", "not stated"):
            self.assertEqual(segments.normalise_role(empty), "", empty)


def world():
    folder = tempfile.mkdtemp()
    rows = []
    for n in range(4):
        rows.append(("recruiters", "recruiting", "I'd pay $30/mo, I track candidates in a spreadsheet", "missed", 3))
    for n in range(5):
        rows.append(("student", "college", "so many apps to check, kind of annoying honestly", "too-many", 1))
    rows.append(("Recruiter", "sales", "I am losing placements because replies get missed", "missed", 2))
    rows.append(("", "beeper", "Beeper keeps disconnecting again and again for me", "too-many", 2))
    rows.append(("ceo", "startups", "One single complaint from a lone chief executive", "missed", 2))
    records, labels = [], []
    for n, (who, community, text, theme, intensity) in enumerate(rows):
        r = store.build_record(source="reddit", native_id="s%d" % n, url="https://reddit.com/s%d" % n, text=text,
                               created="2026-10-01", author="u%d" % n, community=community)
        records.append(r)
        labels.append({"id": r["id"], "relevant": True, "complaint": True, "theme": theme, "new_theme": "", "who": who,
                       "tried": [], "intensity": intensity, "quote": text})
    store.save(os.path.join(folder, "complaints.jsonl"), records)
    store.save(os.path.join(folder, "labels.jsonl"), labels)
    return folder


class Build(unittest.TestCase):
    def setUp(self):
        self.result = segments.build(world(), min_size=2)

    def test_roles_merge_and_rank_by_money(self):
        roles = self.result["roles"]
        self.assertEqual([g["name"] for g in roles], ["recruiter", "student"])
        recruiter = roles[0]
        self.assertEqual((recruiter["complaints"], recruiter["people"], recruiter["money"], recruiter["workaround"]),
                         (5, 5, 4, 4))
        self.assertEqual(recruiter["themes"], {"missed": 5})
        self.assertAlmostEqual(recruiter["mean_intensity"], 2.8)

    def test_small_groups_are_left_out_but_counted(self):
        self.assertEqual(self.result["totals"]["roles_below_min"], 1)

    def test_unknown_role_share(self):
        self.assertEqual(self.result["totals"]["no_role"], 1)
        self.assertEqual(self.result["totals"]["complaints"], 12)

    def test_communities(self):
        names = [g["name"] for g in self.result["communities"]]
        self.assertEqual(names, ["recruiting", "college"])

    def test_examples_are_ids_of_the_group(self):
        ids = set(self.result["roles"][0]["examples"])
        self.assertEqual(len(ids), 3)


class Edges(unittest.TestCase):
    def test_null_author_and_community_case(self):
        folder = world()
        path = os.path.join(folder, "complaints.jsonl")
        records = store.load(path)
        records[0]["author"] = None
        for r in records:
            if r["community"] == "college":
                r["community"] = "College" if r["native_id"] == "s5" else "college"
        store.save(path, records)
        result = segments.build(folder, min_size=2)
        self.assertEqual([g["complaints"] for g in result["communities"] if g["name"] == "college"], [5])


class Cli(unittest.TestCase):
    def test_writes_files(self):
        folder = world()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(segments.main(["--dir", folder, "--min", "2"]), 0)
        with open(os.path.join(folder, "segments.json")) as fh:
            self.assertEqual(json.load(fh)["roles"][0]["name"], "recruiter")
        with open(os.path.join(folder, "segments.md")) as fh:
            md = fh.read()
        self.assertIn("| recruiter | 5 | 5 | 4 | 4 |", md)
        self.assertIn("1 of 12 complaints", md)

    def test_needs_labels(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(segments.main(["--dir", tempfile.mkdtemp()]), 1)


if __name__ == "__main__":
    unittest.main()
