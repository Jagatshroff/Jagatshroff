#!/usr/bin/env python3
"""The Pain Index: score every pain theme with fixed, published rules.

  python3 painindex.py [--dir validator] [--today YYYY-MM-DD]

Reads complaints.jsonl, labels.jsonl, themes.json and idea.json from the state
folder. Writes pain.json, pain.md and signals.jsonl. Same data, same date, same
scores: nothing here is a judgement call.
"""

import argparse
import datetime
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "validate-mine"))

try:
    import store  # noqa: E402
except ImportError:
    sys.exit("error: validate-pain needs the validate-mine folder next to it. Install the whole pack.")
import signals  # noqa: E402
from mdsafe import cite, md as _md  # noqa: E402

RULES_VERSION = 1
WEIGHTS = {"frequency": 20, "breadth": 10, "intensity": 15, "recency": 10, "money": 30, "workaround": 15}
SATURATE = 0.25        # a quarter of a theme's complaints carrying a signal earns full marks for it
RECENT_DAYS = 183      # "recent" means the last six months
FULL_BREADTH = 5       # five communities or more is as broad as it gets
MIN_COMPLAINTS = 10    # below this, a theme is too small to call either way
WORTH_MONEY = (60, 3)  # score at least 60 and at least 3 money signals
REAL = 40
EXAMPLES = 3
DEFAULT_BAR = {"min_complaints": 100, "min_money_signals": 10, "max_age_months": 24}


# Inputs -----------------------------------------------------------------

def _read_json(path, missing_hint):
    if not os.path.exists(path):
        raise ValueError("%s not found. %s" % (os.path.basename(path), missing_hint))
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _months_back(day, months):
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    month += 1
    last = [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return datetime.date(year, month, min(day.day, last))


def _bar(folder):
    path = os.path.join(folder, "idea.json")
    evidence = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            evidence = ((json.load(fh).get("bar") or {}).get("evidence") or {})
    bar = {k: evidence.get(k, v) for k, v in DEFAULT_BAR.items()}
    bad = [k for k, v in bar.items() if type(v) is not int or v < 0]
    if bad:
        raise ValueError("idea.json bar.evidence %s must be whole numbers. Run idea.py check" % ", ".join(bad))
    return bar


def _load(folder):
    records = {r["id"]: r for r in store.load(os.path.join(folder, store.FILE))}
    labels_path = os.path.join(folder, "labels.jsonl")
    if not os.path.exists(labels_path):
        raise ValueError("labels.jsonl not found. Run /validate-cluster first")
    labels = store.load(labels_path)
    themes = _read_json(os.path.join(folder, "themes.json"), "Run /validate-cluster first")
    for label in labels:
        if label.get("complaint") and (type(label.get("intensity")) is not int or not isinstance(label.get("theme"), str)
                                       or not isinstance(label.get("quote"), str)):
            raise ValueError("labels.jsonl has a damaged label for %s. Rerun /validate-cluster tally" % label.get("id"))
    return records, labels, themes["codebook"], themes.get("totals") or {}


# Scoring ----------------------------------------------------------------

def _metrics(items, today):
    n = len(items)
    authors = {r["author"].lower() for r, _, _ in items if r["author"]} | {
        r["id"] for r, _, _ in items if not r["author"]}  # unknown authors each count once
    recent = sum(1 for r, _, _ in items if (today - datetime.date.fromisoformat(r["created"])).days <= RECENT_DAYS)
    return {
        "complaints": n,
        "authors": len(authors),
        "communities": len({r.get("community") or "-" for r, _, _ in items}),
        "mean_intensity": round(sum(l["intensity"] for _, l, _ in items) / n, 3),
        "intense": sum(1 for _, _, s in items if s["intense"]),
        "recent": recent,
        "money": sum(1 for _, _, s in items if s["money"]),
        "workaround": sum(1 for _, _, s in items if s["workaround"]),
        **{kind: sum(1 for _, _, s in items if s[kind]) for kind in signals.MONEY},
        "upvotes": sum(r["score"] or 0 for r, _, _ in items),
    }


def _components(m, largest):
    n = m["complaints"]
    return {
        "frequency": round(math.log1p(n) / math.log1p(largest), 4),
        "breadth": round(0.5 * m["authors"] / n + 0.5 * min(1.0, m["communities"] / FULL_BREADTH), 4),
        "intensity": round(0.7 * (m["mean_intensity"] - 1) / 2 + 0.3 * m["intense"] / n, 4),
        "recency": round(m["recent"] / n, 4),
        "money": round(min(1.0, m["money"] / n / SATURATE), 4),
        "workaround": round(min(1.0, m["workaround"] / n / SATURATE), 4),
    }


def _tier(score, m):
    if m["complaints"] < MIN_COMPLAINTS:
        return "too few to call"
    if score >= WORTH_MONEY[0] and m["money"] >= WORTH_MONEY[1]:
        return "worth money"
    return "real, unproven" if score >= REAL else "noise"


def _examples(items):
    ranked = sorted(items, key=lambda x: (not x[2]["money"], -x[1]["intensity"], -(x[0]["score"] or 0), x[0]["id"]))
    out = []
    for record, label, found in ranked:
        if store.verbatim(label["quote"], record["text"]):  # checked again here: a forged quote never reaches a report
            out.append({"id": record["id"], "quote": label["quote"], "url": record["url"],
                        "signals": [k for k in signals.KINDS if found[k]]})
        if len(out) == EXAMPLES:
            break
    return out


def build(folder, today):
    today = datetime.date.fromisoformat(today)
    records, labels, codebook, coverage = _load(folder)
    bar = _bar(folder)
    since = _months_back(today, bar["max_age_months"])
    scored, too_old = [], 0
    for label in labels:
        record = records.get(label["id"])
        if not label.get("complaint") or not record:
            continue
        if datetime.date.fromisoformat(record["created"]) < since:
            too_old += 1
            continue
        scored.append((record, label, signals.detect(record["text"])))
    groups = {t["key"]: [x for x in scored if x[1]["theme"] == t["key"]] for t in codebook}
    largest = max([len(g) for g in groups.values()] + [1])
    themes = []
    for t in codebook:
        items = groups[t["key"]]
        if not items:
            continue
        m = _metrics(items, today)
        c = _components(m, largest)
        score = round(sum(WEIGHTS[k] * v for k, v in c.items()))
        themes.append({"key": t["key"], "name": t["name"], "definition": t["definition"], "score": score,
                       "tier": _tier(score, m), "components": c, "metrics": m, "examples": _examples(items)})
    themes.sort(key=lambda t: (-t["score"], t["key"]))
    money_total = sum(1 for _, _, s in scored if s["money"])
    return {
        "dir": folder, "today": today.isoformat(), "coverage": {
            k: coverage.get(k) for k in ("in_store", "labeled", "unlabeled") if isinstance(coverage.get(k), int)}, "since": since.isoformat(), "rules_version": RULES_VERSION,
        "weights": WEIGHTS, "themes": themes,
        "totals": {"in_window": len(scored), "too_old": too_old, "money_signals": money_total,
                   "other": sum(1 for _, l, _ in scored if l["theme"] == "other")},
        "bar": {"complaints": {"need": bar["min_complaints"], "have": len(scored),
                               "pass": len(scored) >= bar["min_complaints"]},
                "money_signals": {"need": bar["min_money_signals"], "have": money_total,
                                  "pass": money_total >= bar["min_money_signals"]}},
        "signals": [{"id": r["id"], "theme": l["theme"], "created": r["created"],
                     "signals": {k: s[k] for k in signals.KINDS if s[k]}} for r, l, s in scored],
    }


# Report -----------------------------------------------------------------

def _count(n, one, many=None):
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def _yes(flag):
    return "pass" if flag else "**fail**"


def _coverage_lines(coverage):
    if not coverage.get("unlabeled"):
        return []
    return ["", "**Partial data:** %d of %d mined posts are not labelled yet, so these scores cover only part "
                "of the haul. Finish `/validate-cluster` before trusting the ranking." % (
                    coverage["unlabeled"], coverage.get("in_store") or 0)]


def render(result):
    bar, totals = result["bar"], result["totals"]
    lines = ["# Pain Index", "",
             "%d complaints from %s to %s, scored with rules version %d." % (
                 totals["in_window"], result["since"], result["today"], result["rules_version"]),
             ] + _coverage_lines(result.get("coverage") or {}) + [
             "", "## Against the bar", "", "| evidence | need | have | |", "| --- | --- | --- | --- |",
             "| complaints | %d | %d | %s |" % (bar["complaints"]["need"], bar["complaints"]["have"], _yes(bar["complaints"]["pass"])),
             "| money signals | %d | %d | %s |" % (bar["money_signals"]["need"], bar["money_signals"]["have"],
                                                   _yes(bar["money_signals"]["pass"])),
             "", "## Themes", "",
             "| # | theme | complaints | money | workaround | intensity | score | tier |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for rank, t in enumerate(result["themes"], 1):
        m = t["metrics"]
        lines.append("| %d | %s | %d | %d | %d | %.1f | %d | %s |" % (
            rank, _md(t["name"]), m["complaints"], m["money"], m["workaround"], m["mean_intensity"], t["score"], t["tier"]))
    if totals["other"]:
        lines += ["", "%s still labelled `other`. See `/validate-cluster` to give %s a theme." % (
            _count(totals["other"], "complaint is", "complaints are"), "it" if totals["other"] == 1 else "them")]
    for t in [t for t in result["themes"] if t["examples"]][:EXAMPLES]:
        m = t["metrics"]
        lines += ["", "## %s" % _md(t["name"]), "", _md(t["definition"]), "",
                  "%s from %s in %s. Money: %d would pay, %d already pay, %d price complaints, "
                  "%d switching. Workarounds: %d." % (
                      _count(m["complaints"], "complaint"), _count(m["authors"], "person", "people"),
                      _count(m["communities"], "community", "communities"), m["wtp"], m["spend"], m["price"],
                      m["switch"], m["workaround"]), ""]
        lines += ['> "%s" %s' % (_md(e["quote"]), cite(e["id"], e["url"])) for e in t["examples"]]
    lines += ["", "## How the score works", "",
              "Each theme gets six parts, each from 0 to 1, weighted to a score out of 100:", ""]
    lines += ["- %s: %d" % (k, w) for k, w in WEIGHTS.items()]
    lines += ["", "Money and workaround signals come from fixed word rules in `signals.py`. A quarter of a theme's",
              "complaints carrying a signal earns full marks for it. A theme needs at least %d complaints to be" % MIN_COMPLAINTS,
              "called, and a score of %d with %d money signals to be called worth money." % WORTH_MONEY,
              "Complaints come from the loudest people online. This ranks pains; it does not prove anyone will pay."]
    return "\n".join(lines) + "\n"


def _replace(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def write(result, folder):
    """Build all three outputs first, then swap them in, so a failure never leaves them out of step."""
    report = {k: v for k, v in result.items() if k not in ("signals", "dir")}
    markdown, data = render(result), json.dumps(report, ensure_ascii=False, indent=1)
    store.save(os.path.join(folder, "signals.jsonl"), result["signals"])
    _replace(os.path.join(folder, "pain.json"), data)
    _replace(os.path.join(folder, "pain.md"), markdown)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Score pain themes with fixed rules")
    parser.add_argument("--dir", default=store.DEFAULT_DIR)
    parser.add_argument("--today", default=datetime.date.today().isoformat())
    args = parser.parse_args(argv)
    try:
        result = build(args.dir, args.today)
        write(result, args.dir)
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 1
    for t in result["themes"]:
        print("%3d  %-16s %s" % (t["score"], t["tier"], t["name"]))
    print("wrote %s" % os.path.join(args.dir, "pain.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
