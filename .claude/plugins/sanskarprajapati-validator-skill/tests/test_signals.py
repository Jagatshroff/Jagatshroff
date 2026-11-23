import unittest

from _load import load

signals = load("validate-pain", "signals")


def kinds(text):
    found = signals.detect(text)
    return {k for k in signals.KINDS if found[k]}


class Money(unittest.TestCase):
    def test_would_pay(self):
        for text in ("Honestly I'd pay for this", "I would happily pay $10", "shut up and take my money",
                     "we'd gladly spend 50 a month on it", "willing to pay for something that works"):
            self.assertIn("wtp", kinds(text), text)

    def test_pay_attention_is_not_money(self):
        for text in ("I'd pay attention to the notifications", "you would pay off the debt", "a month ago it broke"):
            self.assertEqual(kinds(text) & set(signals.MONEY), set(), text)

    def test_spend(self):
        for text in ("I'm paying $99/yr for Beeper", "it costs me 15 dollars per month", "we pay for three seats",
                     "€12/mo is fine", "the pro plan", "₹499 a month", "my subscription renewed"):
            self.assertIn("spend", kinds(text), text)

    def test_price_objection(self):
        for text in ("way too expensive for what it is", "Overpriced garbage", "I can't afford another tool",
                     "not worth the money"):
            self.assertIn("price", kinds(text), text)

    def test_switching(self):
        for text in ("I switched from Beeper last week", "cancelled my subscription", "migrated off Texts.com",
                     "asked for a refund"):
            self.assertIn("switch", kinds(text), text)

    def test_switch_on_is_not_switching(self):
        self.assertNotIn("switch", kinds("I have to switch on notifications"))

    def test_review_false_positives(self):
        cases = {
            "I left town for the weekend": "switch",
            "we moved from Texas last year": "switch",
            "I'd spend hours on it every day": "wtp",
            "No one would pay for this": "wtp",
            "nobody would pay for that": "wtp",
            "I lost 10 pounds": "spend",
            "read my business plan": "spend",
        }
        for text, kind in cases.items():
            self.assertNotIn(kind, kinds(text), text)

    def test_curly_apostrophes(self):
        self.assertIn("wtp", kinds("I\u2019d pay for this"))
        self.assertIn("price", kinds("I can\u2019t afford it"))

    def test_long_digit_runs_are_fast(self):
        import time
        for text in ("1," * 20000, "1" * 40000, "$" + "9" * 40000):
            start = time.time()
            signals.detect(text)
            self.assertLess(time.time() - start, 1.0, text[:10])

    def test_money_summary(self):
        self.assertTrue(signals.detect("I'd pay for this")["money"])
        self.assertFalse(signals.detect("it is broken")["money"])


class Workaround(unittest.TestCase):
    def test_workarounds(self):
        for text in ("I track it all in a spreadsheet", "I built my own script for it", "we hacked together a Zapier flow",
                     "I copy-paste every message manually", "hired a VA just to answer DMs", "sticky notes everywhere"):
            self.assertIn("workaround", kinds(text), text)

    def test_not_workarounds(self):
        for text in ("I hate this app", "the manuscript is due", "excellent support", "I made a mistake",
                     "I wrote a post about it", "you will excel at this", "I had a notion it would fail",
                     "moving to VA next year"):
            self.assertNotIn("workaround", kinds(text), text)


class Intensity(unittest.TestCase):
    def test_intense(self):
        for text in ("I HATE this", "it drives me nuts", "absolute nightmare", "so fucking annoying",
                     "why does it break!!!", "THIS IS BROKEN AGAIN", "I'm sick of it"):
            self.assertIn("intense", kinds(text), text)

    def test_calm(self):
        for text in ("It would be nice to have one inbox.", "I use the API and HTML exports", "OK",
                     "our CRM API is fine", "the USA and UK teams"):
            self.assertNotIn("intense", kinds(text), text)


class Evidence(unittest.TestCase):
    def test_hit_shows_the_matched_words(self):
        found = signals.detect("Honestly I'd pay $20 a month for it")
        self.assertEqual(found["wtp"], "I'd pay")
        self.assertEqual(found["spend"], "$20 a month")


if __name__ == "__main__":
    unittest.main()
