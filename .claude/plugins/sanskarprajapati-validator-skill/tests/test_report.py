import contextlib
import io
import json
import os
import unittest

from _load import load
from verdict_world import make, write_json
from test_trial import claim, ready, ruling, run, side_file

report = load("validate-verdict", "report")


def finished(**kw):
    folder = ready(**kw)
    run(folder, "judge")
    code, _, err = ruling(folder, {"ruling": "test", "narrow_to": "", "next_test": "a 200-signup waitlist for recruiters",
                                   "reasons": [{"text": "pain is real and already paid for", "cites": ["D1", "P2"]}]})
    assert code == 0, err
    return folder


def build(folder):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = report.main(["--dir", folder])
    text = ""
    if os.path.exists(os.path.join(folder, "report.md")):
        with open(os.path.join(folder, "report.md")) as fh:
            text = fh.read()
    return code, text, out.getvalue() + err.getvalue()


class Report(unittest.TestCase):
    def test_full_report(self):
        code, text, log = build(finished())
        self.assertEqual(code, 0, log)
        self.assertTrue(text.startswith("# Validation report"))
        self.assertIn("**Verdict: TEST**", text)
        self.assertIn("a 200-signup waitlist for recruiters", text)
        self.assertIn("| complaints | 3 | 4 | pass |", text)
        self.assertIn("| 200 waitlist signups from strangers | not tested |", text)
        self.assertIn("pain is real and already paid for", text)
        self.assertRegex(text, r'"it still drops my WhatsApp every single week" \[R[0-9a-f]{8}\]\(https://')
        self.assertIn("1 claim was struck", text)
        self.assertIn("| Connections drop | 66 | worth money |", text)
        self.assertIn("## Honest limits", text)
        self.assertIn("quotes checked word for word", log)

    def test_bar_moves_are_on_top(self):
        folder = ready()
        lock_path = os.path.join(folder, "idea.lock")
        with open(lock_path) as fh:
            lock = json.load(fh)
        lock["history"] = [{"moved": "2026-10-20", "reason": "narrowed to recruiters", "from": {}, "locked_since": "x"}]
        write_json(lock_path, lock)
        run(folder, "judge")
        ruling(folder, {"ruling": "test", "narrow_to": "", "next_test": "waitlist",
                        "reasons": [{"text": "real", "cites": ["D1"]}]})
        _, text, _ = build(folder)
        head = text.split("## ")[0]
        self.assertIn("The bar was moved", head)
        self.assertIn("narrowed to recruiters", head)

    def test_narrow_says_to_what(self):
        folder = ready()
        run(folder, "judge")
        ruling(folder, {"ruling": "narrow", "narrow_to": "solo recruiters on LinkedIn", "next_test": "10 interviews",
                        "reasons": [{"text": "only recruiters pay", "cites": ["D1"]}]})
        _, text, _ = build(folder)
        self.assertIn("**Verdict: NARROW** to solo recruiters on LinkedIn", text)

    def test_missing_steps_are_listed(self):
        folder = finished()
        os.remove(os.path.join(folder, "gaps.json"))
        _, text, _ = build(folder)
        self.assertIn("Not run: /validate-competitors", text)

    def test_quote_is_cited_to_the_post_it_came_from(self):
        folder, posts = make()
        run(folder, "pack")
        r1, r3 = posts["r1"]["id"], posts["r3"]["id"]
        side_file(folder, "prosecution", [claim("Weak", ["@pain"])])
        side_file(folder, "defense", [claim("Two posts back this", [r1, r3], quote="I keep missing LinkedIn replies")])
        self.assertEqual(run(folder, "check")[0], 0)
        run(folder, "judge")
        ruling(folder, {"ruling": "test", "narrow_to": "", "next_test": "waitlist",
                        "reasons": [{"text": "real", "cites": ["D1"]}]})
        code, text, log = build(folder)
        self.assertEqual(code, 0, log)
        self.assertIn('"I keep missing LinkedIn replies" [%s]' % r3, text)

    def test_a_forged_go_verdict_is_refused(self):
        folder = finished()
        path = os.path.join(folder, "verdict.json")
        with open(path) as fh:
            verdict = json.load(fh)
        verdict["ruling"] = "go"
        verdict["bar"]["real_world"] = True
        write_json(path, verdict)
        code, _, log = build(folder)
        self.assertEqual(code, 1)
        self.assertIn("not allowed", log)

    def test_judge_text_cannot_smuggle_a_quote(self):
        folder = ready()
        run(folder, "judge")
        ruling(folder, {"ruling": "test", "narrow_to": "", "next_test": "waitlist",
                        "reasons": [{"text": 'R1a2b3c4d says "I would happily pay $500 a month"', "cites": ["D1"]}]})
        code, text, log = build(folder)
        self.assertNotIn('"I would happily pay $500 a month"', text)

    def test_needs_a_verdict(self):
        folder, _ = make()
        code, _, log = build(folder)
        self.assertEqual(code, 1)
        self.assertIn("trial", log)

    def test_a_tampered_quote_fails_the_build(self):
        folder = finished()
        path = os.path.join(folder, "verdict.json")
        with open(path) as fh:
            verdict = json.load(fh)
        verdict["reasons"][0]["claims"][0]["quote"] = "it drops everything and I hate it"
        write_json(path, verdict)
        code, _, log = build(folder)
        self.assertEqual(code, 1)
        self.assertIn("NOT IN THE POST", log)


if __name__ == "__main__":
    unittest.main()
