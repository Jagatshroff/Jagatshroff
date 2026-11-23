import contextlib
import io
import json
import os
import tempfile
import time
import unittest

from _load import load

wtp = load("validate-wtp", "wtp")
store = load("validate-mine", "store")


def one(text):
    found = wtp.extract(text)
    return found[0] if found else None


class Extract(unittest.TestCase):
    def test_amount_currency_period(self):
        m = one("I'm paying $99/yr for Beeper and it still breaks")
        self.assertEqual((m["amount"], m["currency"], m["period"]), (99.0, "USD", "year"))
        self.assertAlmostEqual(m["monthly_usd"], 8.25)
        self.assertEqual(m["kind"], "pays")

    def test_words_and_other_currencies(self):
        cases = {
            "it costs me 20 bucks a month": (20.0, "USD", "month"),
            "€12/mo is fine": (12.0, "EUR", "month"),
            "₹499 per month for the pro plan": (499.0, "INR", "month"),
            "we pay £1,200 a year": (1200.0, "GBP", "year"),
            "US$15 per seat per month": (15.0, "USD", "month"),
            "they want 9.99 dollars weekly": (9.99, "USD", "week"),
        }
        for text, (amount, currency, period) in cases.items():
            m = one(text)
            self.assertEqual((m["amount"], m["currency"], m["period"]), (amount, currency, period), text)

    def test_seat_flag(self):
        self.assertTrue(one("US$15 per seat per month")["per_seat"])
        self.assertFalse(one("$15 per month")["per_seat"])

    def test_k_suffix(self):
        self.assertEqual(one("we spent $2k a year on tools")["amount"], 2000.0)

    def test_lifetime_has_no_monthly_value(self):
        m = one("I'd pay $150 lifetime, not a subscription")
        self.assertEqual(m["period"], "lifetime")
        self.assertIsNone(m["monthly_usd"])

    def test_unknown_period(self):
        m = one("I would pay $30 for this")
        self.assertIsNone(m["period"])
        self.assertIsNone(m["monthly_usd"])
        self.assertEqual(m["kind"], "would_pay")

    def test_kinds(self):
        self.assertEqual(one("Honestly I'd happily pay $10 a month")["kind"], "would_pay")
        self.assertEqual(one("$99 a year is way too expensive for this")["kind"], "too_expensive")
        self.assertEqual(one("Overpriced at $40/mo")["kind"], "too_expensive")
        self.assertEqual(one("nobody would pay $50 a month for that")["kind"], "too_expensive")
        self.assertEqual(one("the company raised $5 million")["kind"], "mention")

    def test_not_prices(self):
        for text in ("version 2.5 is out", "I have 3 kids", "100% broken", "$ sign", "page 10 of 20"):
            self.assertEqual(wtp.extract(text), [], text)

    def test_several_prices(self):
        self.assertEqual(len(wtp.extract("Beeper is $99/yr, Texts was $15/mo, I'd pay $5/mo")), 3)

    def test_snippet_is_verbatim(self):
        text = "Long story short.   I'm paying $99/yr for Beeper and it keeps dropping WhatsApp every few days."
        m = one(text)
        self.assertTrue(store.verbatim(m["snippet"], text))
        self.assertIn("$99/yr", m["snippet"])

    def test_time_phrases_are_not_periods(self):
        for text in ("$10 a year ago I bought it", "$10 a day later it broke", "$10 a month ago",
                     "$20 once I upgraded", "$15 a week of hell"):
            m = one(text)
            self.assertIsNone(m["period"], text)
            self.assertIsNone(m["monthly_usd"], text)

    def test_each_price_reads_its_own_clause(self):
        found = wtp.extract("X is $30/mo and too expensive, I'd pay $10/mo")
        self.assertEqual([m["kind"] for m in found], ["too_expensive", "would_pay"])
        for text in ("I would pay $20 but not $50", "I'd pay $10, not $50"):
            self.assertEqual([m["kind"] for m in wtp.extract(text)], ["would_pay", "too_expensive"], text)

    def test_negated_paying(self):
        for text in ("I won't be paying $20/mo", "not paying $20/mo for that", "nobody paid $20/mo"):
            self.assertEqual(one(text)["kind"], "too_expensive", text)
        self.assertEqual(one("I don't mind paying $20/mo")["kind"], "pays")

    def test_objection_after_a_comma(self):
        self.assertEqual(one("It's $50/mo, ridiculous")["kind"], "too_expensive")
        self.assertEqual(one("$10 per month, too expensive")["kind"], "too_expensive")

    def test_digit_grouping(self):
        m = one("₹1,00,000/year for the team plan")
        self.assertEqual((m["amount"], m["period"]), (100000.0, "year"))
        self.assertFalse(any(m["amount"] == 1234 for m in wtp.extract("$1,2345 total")))

    def test_more_phrasings(self):
        cases = {"10€/month": (10.0, "EUR", "month"), "it is 5 € a month": (5.0, "EUR", "month"),
                 "$29 pm": (29.0, "USD", "month"), "£300 pa": (300.0, "GBP", "year")}
        for text, expected in cases.items():
            m = one(text)
            self.assertEqual((m["amount"], m["currency"], m["period"]), expected, text)

    def test_price_ranges_share_a_period(self):
        for text in ("$10 to $20 a month", "$10-$20/month", "$10 or $20 per month"):
            found = wtp.extract(text)
            self.assertEqual([m["period"] for m in found], ["month", "month"], text)

    def test_fast_on_hostile_input(self):
        start = time.time()
        wtp.extract("$1," * 20000)
        wtp.extract("9" * 50000)
        self.assertLess(time.time() - start, 1.0)


class Range(unittest.TestCase):
    def mentions(self, kind, values):
        return [{"kind": kind, "monthly_usd": v} for v in values]

    def test_too_few(self):
        result = wtp.price_range(self.mentions("pays", [10, 12]))
        self.assertIsNone(result["low"])
        self.assertIn("too few", result["note"])

    def test_range_from_buyers(self):
        result = wtp.price_range(self.mentions("pays", [5, 8, 10, 12, 15, 20, 25, 30]))
        self.assertEqual((result["low"], result["high"]), (8.0, 20.0))
        self.assertEqual(result["confidence"], "low")

    def test_objections_cap_the_top(self):
        result = wtp.price_range(self.mentions("would_pay", [5, 8, 10, 12, 15, 20, 25, 30]) +
                                 self.mentions("too_expensive", [12, 14, 16]))
        self.assertEqual(result["high"], 14.0)
        self.assertIn("objections", result["note"])

    def test_conflict_is_reported(self):
        result = wtp.price_range(self.mentions("pays", [20, 22, 25, 28, 30]) +
                                 self.mentions("too_expensive", [5, 6, 7]))
        self.assertIn("overlap", result["note"])

    def test_percentile_nearest_rank(self):
        self.assertEqual(wtp.percentile([1, 2, 3, 4], 50), 2)
        self.assertEqual(wtp.percentile([7], 90), 7)


def world():
    folder = tempfile.mkdtemp()
    texts = [
        ("I'm paying $99/yr for Beeper and it still breaks", "too-many-apps", True),
        ("Honestly I'd pay $10 a month for one that works", "too-many-apps", True),
        ("$40/mo is way too expensive for a chat app", "price", True),
        ("This launch costs $5 a month, sign up!", "", False),
    ]
    records, labels = [], []
    for n, (text, theme, relevant) in enumerate(texts, 1):
        r = store.build_record(source="reddit", native_id="w%d" % n, url="https://reddit.com/w%d" % n, text=text,
                               created="2026-10-01", community="beeper")
        records.append(r)
        labels.append({"id": r["id"], "relevant": relevant, "complaint": relevant, "theme": theme, "new_theme": "",
                       "who": "", "tried": [], "intensity": 2 if relevant else 0, "quote": ""})
    store.save(os.path.join(folder, "complaints.jsonl"), records)
    store.save(os.path.join(folder, "labels.jsonl"), labels)
    return folder


class Cli(unittest.TestCase):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = wtp.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_uses_relevant_posts_only(self):
        folder = world()
        self.assertEqual(self.run_main("--dir", folder)[0], 0)
        with open(os.path.join(folder, "wtp.json")) as fh:
            data = json.load(fh)
        self.assertEqual(len(data["mentions"]), 3)
        self.assertEqual(data["counts"], {"would_pay": 1, "pays": 1, "too_expensive": 1, "mention": 0})
        with open(os.path.join(folder, "wtp.md")) as fh:
            md = fh.read()
        self.assertIn("too few", md.lower())
        self.assertIn("Rates used", md)
        self.assertRegex(md, r"\[R[0-9a-f]{8}\]\(https://reddit\.com/w1\)")

    def test_theme_filter(self):
        folder = world()
        self.run_main("--dir", folder, "--theme", "price")
        with open(os.path.join(folder, "wtp.json")) as fh:
            self.assertEqual(len(json.load(fh)["mentions"]), 1)

    def test_needs_labels(self):
        folder = world()
        os.remove(os.path.join(folder, "labels.jsonl"))
        code, _, err = self.run_main("--dir", folder)
        self.assertEqual(code, 1)
        self.assertIn("validate-cluster", err)


if __name__ == "__main__":
    unittest.main()
