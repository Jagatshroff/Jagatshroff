#!/usr/bin/env python3
"""The final report: the verdict first, then everything behind it.

  python3 report.py [--dir validator]

Needs verdict.json (from trial.py rule). Reads every earlier output that exists.
Writes report.md, report.html (the visual report, one self-contained page) and
links.md (every link the run found, grouped by pain theme), then checks every
quote in the state folder word for word. If any fails, all three are removed and
the run exits 1: a report with a false quote is never left behind.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "validate-mine"))

try:
    import store  # noqa: E402
    import quotecheck  # noqa: E402
    from mdsafe import cite, md  # noqa: E402
    from trialpack import read_json  # noqa: E402
    import trial  # noqa: E402
    import linksmd  # noqa: E402
    import reporthtml  # noqa: E402
except ImportError:
    sys.exit("error: validate-verdict needs the rest of the pack next to it. Install the whole pack.")

STEPS = [("/validate-mine", "complaints.jsonl"), ("/validate-cluster", "labels.jsonl"), ("/validate-pain", "pain.json"),
         ("/validate-segment", "segments.json"), ("/validate-wtp", "wtp.json"), ("/validate-competitors", "gaps.json"),
         ("/validate-prospects", "prospects.json"), ("/validate-interview", "interview.md"),
         ("/validate-smoke", "smoke.md")]
LIMITS = """## Honest limits

- Complaints come from the people who post online, on the sites that were mined. They show what hurts, not how
  many would pay.
- Themes and labels come from language models, checked by tools. Counts are close, not exact. Every quote in this
  report was checked word for word against its post.
- Prices people mention are anchors, not purchases. Only a real-world test (signups, preorders) shows demand.
- The trial argues from this evidence only. It cannot know what was never posted."""


def _records(folder):
    records = {r["id"]: r for r in store.load(os.path.join(folder, store.FILE))}
    root = os.path.join(folder, "competitors")
    if os.path.isdir(root):
        for slug in sorted(os.listdir(root)):
            records.update({r["id"]: r for r in store.load(os.path.join(root, slug, store.FILE))})
    return records


def _text(value):
    """Judge and claim text: safe markdown, one line, no quote marks, so it can never pose as a quote."""
    return md(trial.plain(value))


def _head(verdict):
    ruling = verdict["ruling"].upper()
    line = "**Verdict: %s**" % ruling + (" to %s" % _text(verdict["narrow_to"]) if verdict["ruling"] == "narrow" else "")
    bar = verdict["bar"]
    rw = {None: "not tested yet", True: "passed", False: "failed"}[bar["real_world"]]
    lines = ["# Validation report", "", line, "", "Next test: %s" % _text(verdict["next_test"]), "",
             "Evidence bar: %s. Real-world bar: %s." % ("passed" if bar["evidence_pass"] else "failed", rw)]
    for move in verdict.get("bar_moves") or []:
        lines += ["", "**The bar was moved** on %s, after it was first locked on %s. Reason given: %s" % (
            md(move.get("moved", "?")), md(move.get("locked_since", "?")), md(move.get("reason", "")))]
    return lines


def _why(verdict, records):
    lines = ["", "## Why", ""]
    for reason in verdict["reasons"]:
        lines.append("- %s" % _text(reason["text"]))
        for c in reason["claims"]:
            lines.append("  - %s (%s, strength %d): %s Evidence: %s." % (
                md(c["label"]), md(c["side"]), c["strength"], _text(c["claim"]), ", ".join(md(e) for e in c["evidence"])))
            if c.get("quote"):
                # cite the post the quote really came from, not just the first one listed
                target = c.get("quote_id") or next((e for e in c["evidence"] if e in records and
                                                    quotecheck.quote_matches(c["quote"], records[e]["text"])), None)
                if target in records:
                    lines.append('    > "%s" %s' % (md(c["quote"]), cite(target, records[target]["url"])))
    struck = sum(verdict["struck"].values())
    lines += ["", "The prosecution kept %d claims and the defense %d. %d claim%s struck for citing nothing real." % (
        verdict["kept"]["prosecution"], verdict["kept"]["defense"], struck, " was" if struck == 1 else "s were")]
    return lines


def _bar(folder, verdict):
    lines = ["", "## The bar", "", "Set before any data came in.", "", "| evidence | need | have | result |",
             "| --- | --- | --- | --- |"]
    for key, label in (("complaints", "complaints"), ("money_signals", "money signals")):
        row = (verdict["bar"].get("evidence") or {}).get(key)
        if row:
            lines.append("| %s | %s | %s | %s |" % (label, row["need"], row["have"], "pass" if row["pass"] else "fail"))
    wanted = ((read_json(os.path.join(folder, "idea.json"), {}) or {}).get("bar") or {}).get("real_world", [])
    results = {r.get("bar"): r for r in (read_json(os.path.join(folder, "realworld.json"), {}) or {}).get("results", [])}
    lines += ["", "| real-world bar | result |", "| --- | --- |"]
    for item in wanted:
        r = results.get(item)
        lines.append("| %s | %s |" % (md(item), "have %s, %s" % (r["have"], "pass" if r["pass"] else "fail")
                                      if r else "not tested"))
    return lines


def _sections(folder):
    lines = []
    pain = read_json(os.path.join(folder, "pain.json"))
    if pain:
        lines += ["", "## The pain", "", "| theme | score | tier | complaints | money signals |",
                  "| --- | --- | --- | --- | --- |"]
        lines += ["| %s | %d | %s | %d | %d |" % (md(t["name"]), t["score"], t["tier"], t["metrics"]["complaints"],
                                                  t["metrics"]["money"]) for t in pain["themes"]]
    seg = read_json(os.path.join(folder, "segments.json"))
    if seg:
        lines += ["", "## Who", ""]
        lines += ["- %s %s: %d complaints, %d with money talk" % (kind, md(g["name"]), g["complaints"], g["money"])
                  for kind, key in (("role", "roles"), ("community", "communities")) for g in seg.get(key, [])[:3]]
        if os.path.exists(os.path.join(folder, "segment.md")):
            lines.append("- The chosen beachhead and the case for it are in `segment.md`.")
    wtp = read_json(os.path.join(folder, "wtp.json"))
    if wtp:
        r, c = wtp.get("range") or {}, wtp.get("counts") or {}
        price = "$%.2f to $%.2f a month (%s confidence)" % (r["low"], r["high"], r.get("confidence")) \
            if r.get("low") is not None else "no range: %s" % md(r.get("note", ""))
        lines += ["", "## Money", "", "- %s would pay, %s already pay, %s say too expensive." % (
            c.get("would_pay", 0), c.get("pays", 0), c.get("too_expensive", 0)), "- Price: %s." % price]
    gaps = read_json(os.path.join(folder, "gaps.json"))
    if gaps:
        lines += ["", "## Competitors", ""] + ["- %s: %s" % (md(t["name"]), t["status"]) for t in gaps.get("themes", [])]
    return lines


def _coverage(folder):
    stats = store.stats(store.load(os.path.join(folder, store.FILE)))
    missing = [step for step, name in STEPS if not os.path.exists(os.path.join(folder, name))]
    lines = ["", "## Coverage", "", "%d posts mined, from %s to %s, by source: %s. Details in `sources.md`." % (
        stats["total"], stats["first"] or "-", stats["last"] or "-",
        ", ".join("%s %d" % kv for kv in stats["by_source"].items()) or "none")]
    if missing:
        lines.append("Not run: %s." % ", ".join(missing))
    return lines


def render(folder):
    verdict = read_json(os.path.join(folder, "verdict.json"))
    if not verdict:
        raise ValueError("verdict.json not found. Run the trial first (trial.py pack ... rule)")
    allowed = trial.allowed(trial.evidence_status(folder), trial.real_world_status(folder))
    if verdict.get("ruling") not in trial.RULINGS or verdict["ruling"] not in allowed:
        raise ValueError("verdict.json says %r, which is not allowed by the bar as the files stand (allowed: %s). "
                         "Run the trial again" % (verdict.get("ruling"), ", ".join(allowed)))
    verdict = dict(verdict, bar=dict(verdict.get("bar") or {}, evidence_pass=trial.evidence_status(folder),
                                     real_world=trial.real_world_status(folder)))
    records = _records(folder)
    lines = _head(verdict) + _why(verdict, records) + _bar(folder, verdict) + _sections(folder) + _coverage(folder)
    return "\n".join(lines + ["", LIMITS]) + "\n"


OUTPUTS = ("report.md", "report.html", "links.md")


def _remove(folder):
    for name in OUTPUTS:
        try:
            os.remove(os.path.join(folder, name))
        except OSError:
            pass  # never let cleanup hide the real error


def write_all(folder):
    """report.md, report.html and links.md, built from the same checked data."""
    verdict_md = render(folder)  # everything is rendered before any file is written
    verdict = read_json(os.path.join(folder, "verdict.json"))
    texts = {"report.md": verdict_md,
             "report.html": reporthtml.render_html(folder, verdict, _records(folder)),
             "links.md": linksmd.render_links(folder)}
    for name, text in texts.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            fh.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the final validation report")
    parser.add_argument("--dir", default=store.DEFAULT_DIR)
    args = parser.parse_args(argv)
    try:
        write_all(args.dir)
        result = quotecheck.check_folder(args.dir)
    except Exception as err:  # noqa: BLE001  any failure, from any renderer, leaves no partial report
        _remove(args.dir)
        print("error: %s: %s" % (type(err).__name__, err), file=sys.stderr)
        return 1
    except BaseException:
        _remove(args.dir)
        raise
    print("%d quotes checked word for word in %d files." % (result["ok"], result["files"]))
    if result["failed"] or result["unknown"]:
        _remove(args.dir)
        for f in result["failed"]:
            print("NOT IN THE POST  %s:%d  %s  \"%s\"" % (f["file"], f["line"], f["id"], f["quote"]), file=sys.stderr)
        for u in result["unknown"]:
            print("UNKNOWN ID       %s:%d  %s" % (u["file"], u["line"], u["id"]), file=sys.stderr)
        print("No report was kept. Fix the files above, then run this again.", file=sys.stderr)
        return 1
    for name in OUTPUTS:
        print("wrote %s" % os.path.join(args.dir, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
