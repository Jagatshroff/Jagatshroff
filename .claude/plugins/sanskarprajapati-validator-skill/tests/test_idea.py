import copy
import json
import os
import shutil
import tempfile
import unittest

from _load import SKILLS_DIR, load

idea = load("validate-idea", "idea")
EXAMPLE = os.path.join(SKILLS_DIR, "validate-idea", "idea.example.json")


def example():
    with open(EXAMPLE, encoding="utf-8") as fh:
        return json.load(fh)


class Check(unittest.TestCase):
    def test_example_is_valid(self):
        self.assertEqual(idea.problems(example()), [])

    def test_lists_every_problem_at_once(self):
        data = example()
        del data["target"]
        data["search"]["terms"] = []
        data["bar"]["evidence"]["min_complaints"] = 0
        found = idea.problems(data)
        self.assertEqual(len(found), 3, found)
        self.assertTrue(any("target" in p for p in found))
        self.assertTrue(any("search.terms" in p for p in found))
        self.assertTrue(any("min_complaints" in p for p in found))

    def test_real_world_bar_required(self):
        data = example()
        data["bar"]["real_world"] = []
        self.assertTrue(any("real_world" in p for p in idea.problems(data)))

    def test_app_ids_are_digits(self):
        data = example()
        data["search"]["competitor_apps"] = [{"name": "Thing", "app_store_id": "abc"}]
        self.assertTrue(any("app_store_id" in p for p in idea.problems(data)))

    def test_not_an_object(self):
        self.assertEqual(idea.problems([]), ["idea.json must be a JSON object"])


class Lock(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "idea.json")
        shutil.copy(EXAMPLE, self.path)

    def write(self, data):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def test_lock_then_check_passes(self):
        self.assertEqual(idea.main(["lock", self.path]), 0)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "idea.lock")))
        self.assertEqual(idea.main(["check", self.path]), 0)

    def test_moved_bar_fails_check(self):
        idea.main(["lock", self.path])
        data = example()
        data["bar"]["evidence"]["min_complaints"] = 5
        self.write(data)
        self.assertEqual(idea.main(["check", self.path]), 1)

    def test_other_fields_can_change(self):
        idea.main(["lock", self.path])
        data = example()
        data["search"]["terms"].append("one more term")
        self.write(data)
        self.assertEqual(idea.main(["check", self.path]), 0)

    def test_lock_refuses_to_move_bar_silently(self):
        idea.main(["lock", self.path])
        data = copy.deepcopy(example())
        data["bar"]["real_world"] = ["5 signups"]
        self.write(data)
        self.assertEqual(idea.main(["lock", self.path]), 1)

    def test_relock_with_reason_keeps_history(self):
        idea.main(["lock", self.path])
        data = example()
        data["bar"]["real_world"] = ["50 signups from recruiters"]
        self.write(data)
        self.assertEqual(idea.main(["lock", self.path, "--reason", "narrowed to recruiters"]), 0)
        with open(os.path.join(self.dir, "idea.lock"), encoding="utf-8") as fh:
            lock = json.load(fh)
        self.assertEqual(len(lock["history"]), 1)
        self.assertEqual(lock["history"][0]["reason"], "narrowed to recruiters")
        self.assertEqual(lock["bar"]["real_world"], ["50 signups from recruiters"])

    def test_invalid_file_will_not_lock(self):
        self.write({"idea": "x"})
        self.assertEqual(idea.main(["lock", self.path]), 1)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "idea.lock")))

    def test_check_without_lock_says_so(self):
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(idea.main(["check", self.path]), 0)
        self.assertIn("not locked", out.getvalue())

    def test_malformed_lock_is_a_clean_error(self):
        with open(os.path.join(self.dir, "idea.lock"), "w") as fh:
            fh.write('{"locked": "2026-10-26"}')
        self.assertEqual(idea.main(["check", self.path]), 1)
        self.assertEqual(idea.main(["lock", self.path]), 1)

    def test_broken_json(self):
        with open(self.path, "w") as fh:
            fh.write("{oops")
        self.assertEqual(idea.main(["check", self.path]), 1)


if __name__ == "__main__":
    unittest.main()
