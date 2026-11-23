#!/usr/bin/env python3
"""Who is complaining: a fixed table of the people behind the complaints.

  python3 segments.py [--dir validator] [--min 3]

Two cuts of the same complaints: by the role a post states (recruiter, founder)
and by the community it came from (a subreddit, Hacker News, an app's reviews).
Each group gets its size, how many different people, money and workaround
signals, and intensity. Writes segments.json and segments.md.
"""

import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "validate-mine"))
sys.path.insert(0, os.path.join(HERE, "..", "validate-pain"))

try:
    import store  # noqa: E402
    import signals  # noqa: E402
    from mdsafe import md  # noqa: E402
except ImportError:
    sys.exit("error: validate-segment needs validate-mine and validate-pain next to it. Install the whole pack.")

EXAMPLES = 3
KEEP_S = ("business", "sales", "news", "boss", "analysis", "ops", "class", "glass", "press", "series", "species")
NO_ROLE = {"n/a", "na", "unknown", "none", "unspecified", "not stated", "not specified", "-", "user", "person"}


def _singular(word):
    if word.endswith(KEEP_S) or len(word) <= 2:
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("sses", "shes", "ches", "xes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def normalise_role(who):
    role = str(who or "").lower().replace("\u2019", "'").strip()
    role = re.sub(r"^(?:i'?m|i\s+am|as)\s+", "", role)
    role = re.sub(r"[^\w\s/&+-]", "", role).strip()
    role = re.sub(r"^(?:a|an|the)\s+", "", role)
    if role in NO_ROLE:
        return ""
    words = role.split()
    if words:
        words[-1] = _singular(words[-1])
    return " ".join(words)


def _group(items):
    people = {(r.get("author") or "").lower() or r["id"] for r, _, _ in items}
    ranked = sorted(items, key=lambda x: (not x[2]["money"], -x[1]["intensity"], x[0]["id"]))
    return {
        "complaints": len(items),
        "people": len(people),
        "money": sum(1 for _, _, s in items if s["money"]),
        "workaround": sum(1 for _, _, s in items if s["workaround"]),
        "mean_intensity": round(sum(l["intensity"] for _, l, _ in items) / len(items), 2),
        "themes": dict(collections.Counter(l["theme"] for _, l, _ in items).most_common()),
        "examples": [r["id"] for r, _, _ in ranked[:EXAMPLES]],
    }


def _cut(items, key, min_size):
    buckets = collections.defaultdict(list)
    for item in items:
        name = key(item)
        if name:
            buckets[name].append(item)
    kept = [dict(_group(v), name=k) for k, v in buckets.items() if len(v) >= min_size]
    kept.sort(key=lambda g: (-g["money"], -g["complaints"], g["name"]))
    return kept, sum(1 for v in buckets.values() if len(v) < min_size)


def build(folder, min_size=3):
    labels_path = os.path.join(folder, "labels.jsonl")
    if not os.path.exists(labels_path):
        raise ValueError("labels.jsonl not found. Run /validate-cluster first")
    records = {r["id"]: r for r in store.load(os.path.join(folder, store.FILE))}
    items = [(records[l["id"]], l, signals.detect(records[l["id"]]["text"]))
             for l in store.load(labels_path) if l.get("complaint") and l["id"] in records]
    roles, small_roles = _cut(items, lambda x: normalise_role(x[1].get("who")), min_size)
    places, small_places = _cut(items, lambda x: (x[0].get("community") or x[0]["source"]).lower(), min_size)
    return {"min_size": min_size, "roles": roles, "communities": places, "totals": {
        "complaints": len(items), "no_role": sum(1 for x in items if not normalise_role(x[1].get("who"))),
        "roles_below_min": small_roles, "communities_below_min": small_places}}


def _table(title, groups):
    lines = ["", "## %s" % title, "", "| group | complaints | people | money | workaround | intensity | top themes |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for g in groups:
        top = ", ".join("%s %d" % (md(k), v) for k, v in list(g["themes"].items())[:3])
        lines.append("| %s | %d | %d | %d | %d | %.1f | %s |" % (
            md(g["name"]), g["complaints"], g["people"], g["money"], g["workaround"], g["mean_intensity"], top))
    if not groups:
        lines.append("| (none big enough) | | | | | | |")
    return lines


def render(result):
    t = result["totals"]
    lines = ["# Who is complaining", "",
             "%d complaints. %d of %d complaints name no role, so the community cut matters as much as the role "
             "cut. Groups smaller than %d are left out (%d roles, %d communities)." % (
                 t["complaints"], t["no_role"], t["complaints"], result["min_size"], t["roles_below_min"],
                 t["communities_below_min"])]
    lines += _table("By stated role", result["roles"]) + _table("By community", result["communities"])
    lines += ["", "Ranked by money signals, then size. Money and workaround counts use the same rules as the Pain Index."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Table the people behind the complaints")
    parser.add_argument("--dir", default=store.DEFAULT_DIR)
    parser.add_argument("--min", type=int, default=3, help="smallest group to show")
    args = parser.parse_args(argv)
    try:
        result = build(args.dir, max(1, args.min))
        with open(os.path.join(args.dir, "segments.json"), "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=1)
        with open(os.path.join(args.dir, "segments.md"), "w", encoding="utf-8") as fh:
            fh.write(render(result))
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 1
    for g in result["roles"][:5]:
        print("role       %-24s %3d complaints, %d money" % (g["name"], g["complaints"], g["money"]))
    for g in result["communities"][:5]:
        print("community  %-24s %3d complaints, %d money" % (g["name"], g["complaints"], g["money"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
