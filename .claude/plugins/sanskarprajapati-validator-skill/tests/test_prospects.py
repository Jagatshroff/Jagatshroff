import contextlib
import io
import json
import os
import tempfile
import unittest

from _load import load

prospects = load("validate-prospects", "prospects")
store = load("validate-mine", "store")


class World:
    def __init__(self):
        self.dir = tempfile.mkdtemp()
        self.records, self.labels = [], []

    def add(self, author, text, quote, source="reddit", community="recruiting", who="", theme="missed",
            intensity=2, created="2026-10-01", complaint=True):
        n = len(self.records)
        r = store.build_record(source=source, native_id="p%d" % n, url="https://example.com/p%d" % n, text=text,
                               created=created, author=author, community=community)
        self.records.append(r)
        self.labels.append({"id": r["id"], "relevant": complaint, "complaint": complaint, "theme": theme if complaint else "",
                            "new_theme": "", "who": who, "tried": [], "intensity": intensity if complaint else 0,
                            "quote": quote if complaint else ""})
        return r

    def save(self):
        store.save(os.path.join(self.dir, "complaints.jsonl"), self.records)
        store.save(os.path.join(self.dir, "labels.jsonl"), self.labels)
        return self.dir


def standard():
    w = World()
    w.add("ann_r", "I lose placements because LinkedIn replies get missed every week", "LinkedIn replies get missed every week",
          who="recruiter", intensity=3)
    w.add("ann_r", "I'd pay $30/mo for one inbox, honestly, I hate this", "I'd pay $30/mo for one inbox", who="recruiter")
    w.add("bob", "Too many apps to check, it's kind of annoying", "Too many apps to check", community="college",
          theme="too-many", intensity=1)
    w.add("carl_hn", "My inbox setup is a mess and I keep missing client messages", "I keep missing client messages",
          source="hn", community="hn")
    w.add("Rev One", "Beeper banned my WhatsApp account after one day", "banned my WhatsApp account", source="appstore",
          community="Beeper")
    w.add("", "anonymous complaint about missed messages again today", "missed messages again today")
    w.add("[deleted]", "deleted user complaint about missed replies today", "missed replies today")
    w.add("dave", "Launching my unified inbox app today, check it out", "", complaint=False)
    w.add("old_timer", "Back then I missed every reply across my apps", "I missed every reply", created="2024-01-01")
    w.add("AutoModerator", "Weekly thread: I keep missing client messages everywhere", "I keep missing client messages")
    w.add("RemindMeBot", "I will remind you about missed messages in 2 days", "remind you about missed messages")
    return w


class Build(unittest.TestCase):
    def setUp(self):
        self.result = prospects.build(standard().save(), today="2026-10-26")
        self.by_name = {p["handle"]: p for p in self.result["people"]}

    def test_one_row_per_person_with_their_best_quote(self):
        ann = self.by_name["ann_r"]
        self.assertEqual(ann["complaints"], 2)
        self.assertEqual(ann["quote"], "I'd pay $30/mo for one inbox")
        self.assertTrue(ann["money"])
        self.assertEqual(ann["who"], "recruiter")

    def test_ranked_money_first(self):
        self.assertEqual(self.result["people"][0]["handle"], "ann_r")

    def test_unreachable_people_are_left_out(self):
        for gone in ("", "[deleted]", "Rev One", "dave"):
            self.assertNotIn(gone, self.by_name)
        self.assertEqual(self.result["skipped"]["no_handle"], 2)
        self.assertEqual(self.result["skipped"]["source"], 1)

    def test_bots_are_never_prospects(self):
        self.assertNotIn("AutoModerator", self.by_name)
        self.assertNotIn("RemindMeBot", self.by_name)
        self.assertEqual(self.result["skipped"]["bot"], 2)
        self.assertFalse(prospects.is_bot("Abbott"))
        self.assertTrue(prospects.is_bot("sports_bot"))

    def test_money_words_are_shown(self):
        self.assertEqual(self.by_name["ann_r"]["money_words"], ["I'd pay", "$30/mo"])
        self.assertEqual(self.by_name["bob"]["money_words"], [])

    def test_profile_links(self):
        self.assertEqual(self.by_name["ann_r"]["profile"], "https://www.reddit.com/user/ann_r")
        self.assertEqual(self.by_name["carl_hn"]["profile"], "https://news.ycombinator.com/user?id=carl_hn")

    def test_old_posts_are_flagged(self):
        self.assertTrue(self.by_name["old_timer"]["stale"])
        self.assertFalse(self.by_name["ann_r"]["stale"])

    def test_filters(self):
        result = prospects.build(standard().save(), today="2026-10-26", community="college")
        self.assertEqual([p["handle"] for p in result["people"]], ["bob"])
        result = prospects.build(standard().save(), today="2026-10-26", role="recruiters")
        self.assertEqual([p["handle"] for p in result["people"]], ["ann_r"])
        result = prospects.build(standard().save(), today="2026-10-26", theme="too-many")
        self.assertEqual([p["handle"] for p in result["people"]], ["bob"])

    def test_appstore_can_be_included(self):
        result = prospects.build(standard().save(), today="2026-10-26", sources=("reddit", "hn", "appstore"))
        rev = [p for p in result["people"] if p["handle"] == "Rev One"][0]
        self.assertIsNone(rev["profile"])

    def test_do_not_contact(self):
        folder = standard().save()
        with open(os.path.join(folder, "do_not_contact.txt"), "w") as fh:
            fh.write("# people who asked\nANN_R\n")
        result = prospects.build(folder, today="2026-10-26")
        self.assertNotIn("ann_r", [p["handle"] for p in result["people"]])
        self.assertEqual(result["skipped"]["do_not_contact"], 1)

    def test_do_not_contact_accepts_every_common_spelling(self):
        w = standard()
        w.add("jane_doe", "I miss replies from clients every single week", "I miss replies from clients")
        w.add("hn_person", "Every week I miss replies across my apps", "I miss replies across my apps", source="hn",
              community="hn")
        w.add("x_person", "I forget who I owe a reply to across apps", "who I owe a reply to", source="import",
              community="x")
        folder = w.save()
        with open(os.path.join(folder, "do_not_contact.txt"), "w", encoding="utf-8-sig") as fh:
            fh.write("u/jane_doe  # asked on 3/4\nhttps://news.ycombinator.com/user?id=hn_person\n@X_Person\n/u/ann_r\n")
        names = [p["handle"] for p in prospects.build(folder, today="2026-10-26")["people"]]
        for gone in ("jane_doe", "hn_person", "x_person", "ann_r"):
            self.assertNotIn(gone, names)

    def test_same_person_in_different_spellings_is_one_row(self):
        w = World()
        w.add("Foo", "I keep missing client replies across my apps", "I keep missing client replies", source="import")
        w.add("@foo", "Again today I lost a client reply somewhere", "I lost a client reply", source="import")
        result = prospects.build(w.save(), today="2026-10-26")
        self.assertEqual(len(result["people"]), 1)
        self.assertEqual(result["people"][0]["complaints"], 2)

    def test_newest_quote_wins_a_tie(self):
        w = World()
        w.add("eve", "Years ago I lost a client reply in my apps", "I lost a client reply", created="2024-01-01")
        w.add("eve", "Just now I lost a client reply in my apps again", "I lost a client reply in my apps again",
              created="2026-10-20")
        person = prospects.build(w.save(), today="2026-10-26")["people"][0]
        self.assertEqual(person["quote"], "I lost a client reply in my apps again")

    def test_odd_label_values_are_skipped_not_fatal(self):
        w = standard()
        w.labels[0]["intensity"] = "high"
        w.labels[2]["theme"] = None
        result = prospects.build(w.save(), today="2026-10-26")
        self.assertGreaterEqual(result["skipped"]["bad_label"], 1)

    def test_bot_edges(self):
        self.assertFalse(prospects.is_bot("ROBOT"))
        self.assertTrue(prospects.is_bot("Foo-Bot2"))

    def test_sources_are_case_insensitive_and_checked(self):
        self.assertTrue(prospects.build(standard().save(), today="2026-10-26", sources=("Reddit",))["people"])
        with self.assertRaises(ValueError):
            prospects.build(standard().save(), today="2026-10-26", sources=("myspace",))

    def test_emails_and_phones_are_hidden_in_the_report(self):
        w = World()
        w.add("gil", "I keep missing replies, mail me at gil@example.com or +1 415 555 0100 please",
              "I keep missing replies, mail me at gil@example.com or +1 415 555 0100")
        folder = w.save()
        with contextlib.redirect_stdout(io.StringIO()):
            prospects.main(["--dir", folder, "--today", "2026-10-26"])
        with open(os.path.join(folder, "prospects.md")) as fh:
            md = fh.read()
        self.assertNotIn("gil@example.com", md)
        self.assertNotIn("555 0100", md)
        self.assertIn("(email hidden)", md)

    def test_forged_quote_never_shown(self):
        w = standard()
        w.labels[3]["quote"] = "words carl never wrote at all"
        result = prospects.build(w.save(), today="2026-10-26")
        carl = [p for p in result["people"] if p["handle"] == "carl_hn"]
        self.assertEqual(carl, [])
        self.assertEqual(result["skipped"]["no_verified_quote"], 1)

    def test_max(self):
        self.assertEqual(len(prospects.build(standard().save(), today="2026-10-26", limit=2)["people"]), 2)


class Cli(unittest.TestCase):
    def test_writes_files(self):
        folder = standard().save()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(prospects.main(["--dir", folder, "--today", "2026-10-26"]), 0)
        with open(os.path.join(folder, "prospects.md")) as fh:
            md = fh.read()
        self.assertIn("[ann\\_r](https://www.reddit.com/user/ann_r)", md)
        self.assertIn('"I\'d pay $30/mo for one inbox"', md)
        self.assertIn("yes: I'd pay, $30/mo", md)
        self.assertIn("Never message", md)
        with open(os.path.join(folder, "prospects.json")) as fh:
            self.assertEqual(json.load(fh)["people"][0]["handle"], "ann_r")

    def test_needs_labels(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(prospects.main(["--dir", tempfile.mkdtemp()]), 1)


if __name__ == "__main__":
    unittest.main()
