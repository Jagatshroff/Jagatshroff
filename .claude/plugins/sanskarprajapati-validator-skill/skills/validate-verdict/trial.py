#!/usr/bin/env python3
"""The trial: a prosecutor and a defense argue from evidence, a judge rules within the bar.

  python3 trial.py pack  [--fresh]        evidence pack + prosecution and defense briefs
  python3 trial.py save  prosecution|defense|ruling < reply.txt
  python3 trial.py check                  strike every claim that cites nothing real
  python3 trial.py judge                  judge brief with the surviving claims only
  python3 trial.py rule                   check the ruling against the bar, write verdict.json

Global flag first: --dir validator. Works in validator/trial/.
"""

import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "validate-mine"))

try:
    import store  # noqa: E402
    import trialpack  # noqa: E402
    from quotecheck import ID, _texts, quote_matches  # noqa: E402
except ImportError:
    sys.exit("error: validate-verdict needs the rest of the pack next to it. Install the whole pack.")

SIDES = ("prosecution", "defense")
RULINGS = ("go", "test", "narrow", "kill")
MAX_CLAIM = 600


class Paths:
    def __init__(self, folder):
        self.dir = os.path.abspath(folder)
        self.trial = os.path.join(self.dir, "trial")
        self.evidence = os.path.join(self.trial, "evidence.md")
        self.checked = os.path.join(self.trial, "checked.json")
        self.ruling = os.path.join(self.trial, "ruling.json")
        self.verdict = os.path.join(self.dir, "verdict.json")

    def side(self, side):
        return os.path.join(self.trial, side + ".json")

    def brief(self, name):
        return os.path.join(self.trial, "briefs", name + ".md")


class Evidence:
    """What a claim may cite: post IDs in any store, and the reports that exist."""

    def __init__(self, folder):
        self.texts = _texts(folder)
        self.tokens = trialpack.tokens(folder)


# The bar -----------------------------------------------------------------

def evidence_status(folder):
    bar = (trialpack.read_json(os.path.join(folder, "pain.json"), {}) or {}).get("bar")
    if not bar:
        raise ValueError("pain.json not found. Run /validate-pain first")
    return bar["complaints"]["pass"] is True and bar["money_signals"]["pass"] is True


def real_world_status(folder):
    """True: every real-world bar was tested and passed. False: any failed. None: not (fully) tested."""
    data = trialpack.read_json(os.path.join(folder, "realworld.json"))
    if data is None:
        return None
    wanted = ((trialpack.read_json(os.path.join(folder, "idea.json"), {}) or {}).get("bar") or {}).get("real_world", [])
    results = {}
    for r in data.get("results", []) if isinstance(data, dict) else []:
        if not isinstance(r, dict) or not isinstance(r.get("pass"), bool) or \
                any(type(r.get(k)) not in (int, float) for k in ("have", "need")):
            raise ValueError("realworld.json: every result needs a bar, numbers in 'need' and 'have', "
                             "and true/false in 'pass'")
        if r.get("bar") not in wanted:
            raise ValueError("realworld.json: %r is not in idea.json bar.real_world. Copy it exactly" % r.get("bar"))
        if r["bar"] in results:
            raise ValueError("realworld.json: %r is listed twice" % r["bar"])
        if r["pass"] != (r["have"] >= r["need"]):
            raise ValueError("realworld.json: %r says pass=%s but has %s of %s. The tool counts pass from the "
                             "numbers, never from the label" % (r["bar"], r["pass"], r["have"], r["need"]))
        results[r["bar"]] = r
    if any(not r["pass"] for r in results.values()):
        return False
    return True if wanted and all(w in results for w in wanted) else None


def allowed(evidence_pass, rw):
    if not evidence_pass or rw is False:
        return ["narrow", "kill"]
    return ["go", "narrow", "kill"] if rw else ["test", "narrow", "kill"]


# Striking ---------------------------------------------------------------

def _issue(c, ev):
    if not isinstance(c, dict) or not str(c.get("claim") or "").strip():
        return "empty claim"
    if len(str(c["claim"])) > MAX_CLAIM:
        return "claim is longer than %d characters" % MAX_CLAIM
    if type(c.get("strength")) is not int or c["strength"] not in (1, 2, 3):
        return "strength must be 1, 2 or 3"
    cites = c.get("evidence")
    if not isinstance(cites, list) or not cites:
        return "no evidence cited"
    for item in cites:
        item = str(item)
        if item.startswith("@"):
            if item not in ev.tokens:
                return "unknown source %s (no such report in the pack)" % item
        elif not ID.fullmatch(item) or item not in ev.texts:
            return "unknown id %s" % item
    if c.get("quote") is not None and not isinstance(c.get("quote"), str):
        return "quote must be text"
    if c.get("quote") and not quote_source(c, ev.texts):
        return "quote is not word for word from any post it cites"
    return None


_QUOTE_MARKS = str.maketrans({'"': "", "\u201c": "", "\u201d": "", "\u2018": "'", "\u2019": "'", "\u00ab": "",
                              "\u00bb": "", "`": ""})


def plain(text):
    """One line, no quote marks: claim text can neither forge brief structure nor pose as a quote."""
    return " ".join(str(text).translate(_QUOTE_MARKS).split())


def quote_source(c, texts):
    """The cited post a claim's quote actually comes from, or None."""
    quote = c.get("quote") or ""
    return next((str(i) for i in c.get("evidence") or [] if not str(i).startswith("@")
                 and quote_matches(quote, texts.get(str(i), ""))), None) if quote else None


def strike(claims, ev):
    """(kept, struck): a claim survives only if everything it cites is real."""
    kept, struck = [], []
    for c in claims if isinstance(claims, list) else []:
        reason = _issue(c, ev)
        if reason:
            struck.append({"claim": str((c or {}).get("claim", ""))[:200] if isinstance(c, dict) else "", "reason": reason})
        else:
            kept.append({"claim": plain(c["claim"]), "evidence": [str(i) for i in c["evidence"]],
                         "quote": " ".join((c.get("quote") or "").split()), "quote_id": quote_source(c, ev.texts),
                         "strength": c["strength"]})
    return kept, struck


# Commands ---------------------------------------------------------------

def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)


def parse_reply(text):
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = fenced.group(1) if fenced else text
    start, end = body.find("{"), body.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("no JSON object found in the reply")
    return json.loads(body[start:end])


def cmd_pack(paths, fresh):
    if os.path.isdir(paths.trial) and not fresh:
        raise ValueError("a trial already exists in %s. Use --fresh to start over" % paths.trial)
    ev_pass, rw = evidence_status(paths.dir), real_world_status(paths.dir)
    if fresh and os.path.isdir(paths.trial):
        shutil.rmtree(paths.trial)
    trialpack.write_pack(paths, ev_pass, rw)
    print("wrote %s" % paths.evidence)
    for side in SIDES:
        print("  %s" % paths.brief(side))
    print("allowed rulings: %s" % ", ".join(allowed(ev_pass, rw)))


def _forget_check(paths):
    """Any change to the sides makes the old check worthless."""
    if os.path.exists(paths.checked):
        os.remove(paths.checked)


def cmd_check(paths):
    _forget_check(paths)
    ev, checked, missing = Evidence(paths.dir), {}, []
    for side in SIDES:
        data = trialpack.read_json(paths.side(side))
        if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
            missing.append(side)
            continue
        kept, struck = strike(data["claims"], ev)
        checked[side] = {"kept": kept, "struck": struck}
        print("%s: %d kept, %d struck" % (side, len(kept), len(struck)))
        for s in struck:
            print("  struck: %s (%s)" % (s["claim"][:70], s["reason"]))
    for side in missing:
        print("%s: no valid claims file yet (%s)" % (side, paths.side(side)))
    if missing:
        return 1
    _write(paths.checked, checked)
    return 0


def _labels(checked):
    out = {}
    for side, prefix in (("prosecution", "P"), ("defense", "D")):
        for n, c in enumerate(checked[side]["kept"], 1):
            out["%s%d" % (prefix, n)] = dict(c, side=side, label="%s%d" % (prefix, n))
    return out


def cmd_judge(paths):
    checked = trialpack.read_json(paths.checked)
    if not checked:
        raise ValueError("run check first")
    ev_pass, rw = evidence_status(paths.dir), real_world_status(paths.dir)
    trialpack.write_judge(paths, checked, allowed(ev_pass, rw), ev_pass, rw)
    print("wrote %s" % paths.brief("judge"))


def _ruling_problems(data, labels, allowed_list):
    if not isinstance(data, dict):
        return ["the ruling must be a JSON object"]
    out = []
    ruling = data.get("ruling")
    if ruling not in RULINGS:
        return ["ruling must be one of %s" % ", ".join(RULINGS)]
    if ruling not in allowed_list:
        out.append("ruling %r is not allowed by the bar; allowed: %s" % (ruling, ", ".join(allowed_list)))
    reasons = data.get("reasons")
    if not isinstance(reasons, list) or not reasons:
        return out + ["give at least one reason"]
    if ruling == "kill" and len(reasons) < 2:
        out.append("kill needs at least two reasons")
    if ruling == "narrow" and not str(data.get("narrow_to") or "").strip():
        out.append("narrow needs narrow_to: the group and the pain")
    if not str(data.get("next_test") or "").strip():
        out.append("next_test is required")
    for n, reason in enumerate(reasons, 1):
        cites = reason.get("cites") if isinstance(reason, dict) else None
        if not isinstance(cites, list) or not cites or not str(reason.get("text") or "").strip():
            out.append("reason %d needs text and at least one cited claim" % n)
            continue
        bad = [c for c in cites if c not in labels]
        if bad:
            out.append("reason %d cites claims that do not exist or were struck: %s" % (n, ", ".join(map(str, bad))))
    return out


def cmd_rule(paths):
    checked = trialpack.read_json(paths.checked)
    data = trialpack.read_json(paths.ruling)
    if not checked or data is None:
        raise ValueError("needs trial/checked.json (run check) and trial/ruling.json (the judge's answer)")
    ev_pass, rw = evidence_status(paths.dir), real_world_status(paths.dir)
    labels, allowed_list = _labels(checked), allowed(ev_pass, rw)
    problems = _ruling_problems(data, labels, allowed_list)
    if problems:
        raise ValueError("ruling refused:\n- " + "\n- ".join(problems))
    lock = trialpack.read_json(os.path.join(paths.dir, "idea.lock"), {}) or {}
    verdict = {
        "ruling": data["ruling"], "narrow_to": str(data.get("narrow_to") or ""), "next_test": str(data["next_test"]),
        "reasons": [{"text": r["text"], "cites": r["cites"], "claims": [labels[c] for c in r["cites"]]}
                    for r in data["reasons"]],
        "allowed": allowed_list,
        "bar": {"evidence_pass": ev_pass, "real_world": rw,
                "evidence": (trialpack.read_json(os.path.join(paths.dir, "pain.json"), {}) or {}).get("bar")},
        "bar_moves": lock.get("history") or [],
        "kept": {s: len(checked[s]["kept"]) for s in SIDES},
        "struck": {s: len(checked[s]["struck"]) for s in SIDES},
    }
    _write(paths.verdict, verdict)
    print("verdict: %s. Wrote %s" % (verdict["ruling"], paths.verdict))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Put the idea on trial")
    parser.add_argument("--dir", default=store.DEFAULT_DIR)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pack").add_argument("--fresh", action="store_true")
    sub.add_parser("save").add_argument("what")
    for name in ("check", "judge", "rule"):
        sub.add_parser(name)
    args = parser.parse_args(argv)
    paths = Paths(args.dir)
    try:
        if args.cmd == "pack":
            cmd_pack(paths, args.fresh)
        elif args.cmd == "check":
            return cmd_check(paths)
        elif args.cmd == "judge":
            cmd_judge(paths)
        elif args.cmd == "rule":
            cmd_rule(paths)
        else:
            if args.what not in SIDES + ("ruling",):
                raise ValueError("save prosecution, defense or ruling")
            data = parse_reply(sys.stdin.read())
            if args.what != "ruling":
                _forget_check(paths)
            _write(paths.ruling if args.what == "ruling" else paths.side(args.what), data)
            print("saved %s" % args.what)
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
