#!/usr/bin/env python3
"""The Price Reader: every price people mention, turned into a range from real words.

  python3 wtp.py [--dir validator] [--theme KEY] [--community NAME] [--all-posts]

Reads complaints.jsonl and labels.jsonl. Looks at relevant posts only, unless
--all-posts. Writes wtp.json and wtp.md.
"""

import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "validate-mine"))

try:
    import store  # noqa: E402
    from mdsafe import cite, md  # noqa: E402
except ImportError:
    sys.exit("error: validate-wtp needs the validate-mine folder next to it. Install the whole pack.")

# Approximate rates to USD, fixed so the same data always gives the same range.
RATES_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "INR": 0.012, "CAD": 0.73, "AUD": 0.66}
RATES_AS_OF = "2026-10"
MIN_BUYERS = 5
CONFIDENCE = ((40, "high"), (15, "medium"), (0, "low"))

_NUM = r"\d{1,6}(?:,\d{2,3}){0,3}(?:\.\d{1,2})?(?!\d)(?!,\d)"  # 1,200 and Indian 1,00,000; never half a number
_PRICE = re.compile(
    r"(?<![\w.,$€£₹])(?P<cur>(?:us|ca|au|a)?\$|€|£|₹|rs\.?\s?|(?:usd|eur|gbp|inr|cad|aud)\s?)(?P<num>" + _NUM
    + r")(?P<k>k\b)?"
    r"|(?<![\w.,])(?P<num2>" + _NUM + r")(?P<k2>k)?\s?(?P<cur2>dollars?|bucks|usd|euros?|eur|gbp|rupees?|inr|cad|aud)\b"
    r"|(?<![\w.,])(?P<num3>" + _NUM + r")\s?(?P<cur3>€|£|₹|\$)(?!\w)",
    re.I)
_NOT_TIME = r"(?!\s+(?:ago|later|before|back|earlier|after|of)\b)"  # "$10 a year ago" is a story, not a price
_PERIOD = re.compile(
    r"\s*(?:/\s*|(?:per|a|an|each|every)\s+)(?P<unit>mo(?:nth)?s?|yr|years?|annum|wk|weeks?|days?|seats?|users?"
    r"|licen[cs]es?|lifetime)\b" + _NOT_TIME
    + r"|\s+(?P<adv>monthly|yearly|annually|weekly|daily|one[- ]time|lifetime)\b"
    r"|\s+(?P<abbr>pm|p/m|pcm|pa|p\.a\.)(?![\w/])", re.I)
_BIG = re.compile(r"\s?(?:million|billion|mn|bn|m)\b", re.I)
_JOINS_RANGE = re.compile("\\s*(?:-|\u2013|\u2014|to|or)\\s*", re.I)  # hyphen, en dash, em dash, to, or
_UNITS = {"mo": "month", "month": "month", "monthly": "month", "yr": "year", "year": "year", "annum": "year",
          "yearly": "year", "annually": "year", "wk": "week", "week": "week", "weekly": "week", "day": "day",
          "daily": "day", "lifetime": "lifetime", "one-time": "lifetime", "one time": "lifetime",
          "pm": "month", "p/m": "month", "pcm": "month", "pa": "year", "p.a.": "year"}
_PER_MONTH = {"month": 1.0, "year": 1 / 12, "week": 52 / 12, "day": 365 / 12}
_CURRENCY = [(r"^ca\$|^cad", "CAD"), (r"^a\$|^au\$|^aud", "AUD"), (r"^\$|^us\$|^usd|^dollar|^buck", "USD"),
             (r"^€|^eur", "EUR"), (r"^£|^gbp", "GBP"), (r"^₹|^rs|^inr|^rupee", "INR")]
_CURLY = str.maketrans({"‘": "'", "’": "'"})

_OBJECTION = re.compile(r"too\s+expensive|overpriced|not\s+worth|can'?t\s+afford|too\s+much|\bsteep\b|ridiculous"
                        r"|rip[- ]?off|price\s+hike|raised\s+(?:the|their|its)\s+price|way\s+more\s+than")
_NO_PAY = re.compile(r"\b(?:nobody|no\s+one|noone|never|wouldn'?t|won'?t|not|don'?t|doesn'?t)\s+(?!mind\b)"
                     r"(?:\w+\s+){0,2}(?:pay\w*|paid|spen[dt]\w*)\b")
_NEG_END = re.compile(r"(?:\bnot|\bnever|n't)\s*$")
_WOULD = re.compile(r"\b(?:i'?d|i\s+would|we'?d|we\s+would|willing\s+to|happy\s+to|ready\s+to|gladly|happily"
                    r"|i'?ll|we'?ll)\s+(?:\w+\s+){0,2}(?:pay|spend)\b|take\s+my\s+money|would\s+be\s+worth")
_PAYS = re.compile(r"\b(?:paying|pay|paid|costs?|spen[dt]|subscri\w+|plan|bill(?:ed)?|charg\w+)\b")
_CLAUSE = re.compile(r"[.!?;\n]|\bbut\b|\bhowever\b|\bthough\b")


def _currency(raw):
    raw = raw.strip().lower()
    for pattern, code in _CURRENCY:
        if re.match(pattern, raw):
            return code
    return "USD"


def _period(text, end):
    """Up to two period phrases after the price: '/yr', 'per seat per month', 'monthly', 'pm'."""
    period, per_seat = None, False
    for _ in range(2):
        match = _PERIOD.match(text, end)
        if not match:
            break
        word = (match.group("unit") or match.group("adv") or match.group("abbr")).lower()
        if word.startswith(("seat", "user", "licen")):
            per_seat = True
        else:
            period = _UNITS.get(word, _UNITS.get(word.rstrip("s"), period))
        end = match.end()
    return period, per_seat, end


def _kind(text, start, end, prev_end, next_start):
    """What the words around this one price say. Each price reads only its own clause:
    the window stops at the previous price, at 'but', and at the end of the sentence."""
    before = _CLAUSE.split(text[max(prev_end, start - 80):start].lower().translate(_CURLY))[-1]
    near = before.split(",")[-1]
    after = text[end:min(next_start, end + 50)].lower().translate(_CURLY).lstrip(" ,;:-\u2013\u2014")
    after = re.split(r"[.,!?;\n]|\bbut\b", after)[0]
    if _NEG_END.search(near) or _NO_PAY.search(near):
        return "too_expensive"
    if _WOULD.search(near):
        return "would_pay"
    if _OBJECTION.search(near) or _NO_PAY.search(before):
        return "too_expensive"
    if _WOULD.search(before):
        return "would_pay"
    if _OBJECTION.search(before) or _OBJECTION.search(after):
        return "too_expensive"
    if _PAYS.search(before) or _PAYS.search(after):
        return "pays"
    return "mention"


def _snippet(text, start, end):
    a, b = max(0, start - 70), min(len(text), end + 50)
    if a > 0 and not text[a - 1].isspace():
        nxt = re.search(r"\s", text[a:start])
        a = a + nxt.end() if nxt else start
    if b < len(text) and not text[b].isspace():
        prev = [m.start() for m in re.finditer(r"\s", text[end:b])]
        b = end + prev[-1] if prev else end
    return " ".join(text[a:b].split())


def _monthly(amount, currency, period, big):
    if period in _PER_MONTH and not big:
        return round(amount * RATES_USD[currency] * _PER_MONTH[period], 2)
    return None


def _raw_prices(text):
    out = []
    for match in _PRICE.finditer(text):
        raw_num = match.group("num") or match.group("num2") or match.group("num3")
        amount = float(raw_num.replace(",", "")) * (1000 if (match.group("k") or match.group("k2")) else 1)
        currency = _currency(match.group("cur") or match.group("cur2") or match.group("cur3"))
        period, per_seat, end = _period(text, match.end())
        out.append({"start": match.start(), "end": end, "amount": amount, "currency": currency, "period": period,
                    "per_seat": per_seat, "big": bool(_BIG.match(text, match.end()))})
    return out


def _share_range_periods(text, prices):
    """'$10 to $20 a month': the first price takes the second one's period."""
    shared = [dict(p) for p in prices]
    for i in range(len(shared) - 2, -1, -1):
        here, nxt = shared[i], shared[i + 1]
        if here["period"] is None and nxt["period"] and _JOINS_RANGE.fullmatch(text[here["end"]:nxt["start"]]):
            here["period"], here["per_seat"] = nxt["period"], nxt["per_seat"]
    return shared


def extract(text):
    """Every price in the text, with what it is, per month in USD where that is knowable."""
    text = (text or "")[:20000]
    prices = _share_range_periods(text, _raw_prices(text))
    found = []
    for i, p in enumerate(prices):
        prev_end = prices[i - 1]["end"] if i else 0
        next_start = prices[i + 1]["start"] if i + 1 < len(prices) else len(text)
        found.append({
            "amount": p["amount"], "currency": p["currency"], "period": p["period"], "per_seat": p["per_seat"],
            "monthly_usd": _monthly(p["amount"], p["currency"], p["period"], p["big"]),
            "kind": "mention" if p["big"] else _kind(text, p["start"], p["end"], prev_end, next_start),
            "written": " ".join(text[p["start"]:p["end"]].split()), "snippet": _snippet(text, p["start"], p["end"]),
        })
    return found


# Range ------------------------------------------------------------------

def percentile(values, pct):
    """Nearest-rank percentile: always one of the real values, never an interpolation."""
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def price_range(mentions):
    buyers = [m["monthly_usd"] for m in mentions if m["kind"] in ("would_pay", "pays") and m["monthly_usd"] is not None]
    objections = [m["monthly_usd"] for m in mentions if m["kind"] == "too_expensive" and m["monthly_usd"] is not None]
    if len(buyers) < MIN_BUYERS:
        return {"low": None, "high": None, "confidence": None, "buyers": len(buyers), "objections": len(objections),
                "note": "too few monthly prices from buyers (%d, need %d) to call a range" % (len(buyers), MIN_BUYERS)}
    low, high = float(percentile(buyers, 25)), float(percentile(buyers, 75))
    notes = ["middle half of what buyers pay or would pay"]
    if len(objections) >= 3:
        ceiling = float(percentile(objections, 50))
        if ceiling < low:
            notes.append("objections start below what buyers pay (median %.2f), so the groups overlap: "
                         "check who is objecting" % ceiling)
            high = low
        elif ceiling < high:
            notes.append("capped at the median of price objections")
            high = ceiling
    confidence = next(label for floor, label in CONFIDENCE if len(buyers) >= floor)
    return {"low": low, "high": high, "confidence": confidence, "buyers": len(buyers), "objections": len(objections),
            "note": "; ".join(notes)}


# Report -----------------------------------------------------------------

def _load(folder, theme, community, all_posts):
    labels_path = os.path.join(folder, "labels.jsonl")
    if not os.path.exists(labels_path):
        raise ValueError("labels.jsonl not found. Run /validate-cluster first")
    labels = {l["id"]: l for l in store.load(labels_path)}
    for record in store.load(os.path.join(folder, store.FILE)):
        label = labels.get(record["id"])
        if not label or (not all_posts and not label.get("relevant")):
            continue
        if theme and label.get("theme") != theme:
            continue
        if community and (record.get("community") or "").lower() != community.lower():
            continue
        yield record, label


def build(folder, theme=None, community=None, all_posts=False):
    mentions = []
    for record, label in _load(folder, theme, community, all_posts):
        for m in extract(record["text"]):
            mentions.append(dict(m, id=record["id"], url=record["url"], theme=label.get("theme") or "",
                                 created=record["created"]))
    counts = {k: sum(1 for m in mentions if m["kind"] == k) for k in ("would_pay", "pays", "too_expensive", "mention")}
    return {"filter": {"theme": theme, "community": community, "all_posts": all_posts}, "counts": counts,
            "range": price_range(mentions), "rates_usd": RATES_USD, "rates_as_of": RATES_AS_OF, "mentions": mentions}


def render(result, text_by_id):
    r, c = result["range"], result["counts"]
    lines = ["# Price Reader", "",
             "%d price mentions: %d would pay, %d already pay, %d too expensive, %d other mentions." % (
                 len(result["mentions"]), c["would_pay"], c["pays"], c["too_expensive"], c["mention"]), ""]
    if r["low"] is None:
        lines.append("**Range:** none. %s." % r["note"].capitalize())
    else:
        lines.append("**Range:** $%.2f to $%.2f a month (%s confidence, %d buyer prices, %d objections). %s." % (
            r["low"], r["high"], r["confidence"], r["buyers"], r["objections"], r["note"].capitalize()))
    lines += ["", "| kind | as written | USD a month | where |", "| --- | --- | --- | --- |"]
    order = {"would_pay": 0, "pays": 1, "too_expensive": 2, "mention": 3}
    for m in sorted(result["mentions"], key=lambda m: (order[m["kind"]], -(m["monthly_usd"] or 0), m["id"])):
        monthly = "-" if m["monthly_usd"] is None else "%.2f%s" % (m["monthly_usd"], " per seat" if m["per_seat"] else "")
        lines.append("| %s | %s | %s | %s |" % (m["kind"].replace("_", " "), md(m["written"]), monthly, cite(m["id"], m["url"])))
    quoted = [m for m in result["mentions"] if store.verbatim(m["snippet"], text_by_id.get(m["id"], ""))]
    if quoted:
        lines += ["", "## In their words", ""]
        lines += ['> "%s" %s' % (md(m["snippet"]), cite(m["id"], m["url"])) for m in quoted[:12]]
    lines += ["", "Rates used (to USD, as of %s): %s. Yearly prices are divided by 12, weekly ones multiplied by "
                  "52/12. Lifetime prices and prices with no period are listed but left out of the range." % (
                      result["rates_as_of"], ", ".join("%s %s" % kv for kv in sorted(result["rates_usd"].items())))]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read every price people mention")
    parser.add_argument("--dir", default=store.DEFAULT_DIR)
    parser.add_argument("--theme")
    parser.add_argument("--community")
    parser.add_argument("--all-posts", action="store_true", help="include posts labelled not relevant")
    args = parser.parse_args(argv)
    try:
        result = build(args.dir, args.theme, args.community, args.all_posts)
        text_by_id = {r["id"]: r["text"] for r in store.load(os.path.join(args.dir, store.FILE))}
        with open(os.path.join(args.dir, "wtp.json"), "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=1)
        with open(os.path.join(args.dir, "wtp.md"), "w", encoding="utf-8") as fh:
            fh.write(render(result, text_by_id))
    except (ValueError, OSError, KeyError, TypeError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 1
    print(json.dumps({"counts": result["counts"], "range": result["range"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
