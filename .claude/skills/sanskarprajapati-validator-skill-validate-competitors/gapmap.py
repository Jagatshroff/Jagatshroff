#!/usr/bin/env python3
"""The gap map: your pain themes against what each competitor's own users complain about.

  python3 gapmap.py [--dir validator]

Every competitor lives in validator/competitors/<slug>/, mined and labelled with
the same codebook as the main run (see the skill). Reads pain.json if it exists.
Writes gaps.json and gaps.md.
"""

import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "validate-mine"))

try:
    import store  # noqa: E402
    from mdsafe import cite, md  # noqa: E402
except ImportError:
    sys.exit("error: validate-competitors needs the validate-mine folder next to it. Install the whole pack.")

GAP_SHARE = 0.10     # a theme in a tenth or more of a competitor's complaints is a live problem for them
SILENT_SHARE = 0.03  # under 3% everywhere, with enough data, and they may have solved it
MIN_COMPLAINTS = 20  # fewer complaints than this and silence proves nothing
LIVE_TIERS = ("worth money", "real, unproven")
STATUS_ORDER = ("open gap", "they struggle too", "unclear", "maybe solved")
EXAMPLES = 2


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _keys(codebook):
    return {t["key"] for t in codebook["themes"]}


def _load_competitor(folder, slug, keys):
    themes_path = os.path.join(folder, "themes.json")
    book_path = os.path.join(folder, "cluster_codebook.json")
    if not os.path.exists(themes_path) or not os.path.exists(book_path):
        raise ValueError("competitor %r is not labelled yet: run batches.py tally with --dir %s" % (slug, folder))
    if _keys(_read_json(book_path)) != keys:
        raise ValueError("competitor %r was labelled with a different codebook. Copy the main "
                         "cluster_codebook.json into %s and label it again" % (slug, folder))
    themes = _read_json(themes_path)
    total = (themes.get("totals") or {}).get("complaints") or 0
    counts = {t["key"]: t.get("count", 0) for t in themes.get("themes", [])}
    other = collections.Counter(o["new_theme"].strip().lower() for o in themes.get("other") or []
                                if isinstance(o, dict) and isinstance(o.get("new_theme"), str) and o["new_theme"].strip())
    records = {r["id"]: r for r in store.load(os.path.join(folder, store.FILE))}
    labels = [l for l in store.load(os.path.join(folder, "labels.jsonl")) if l.get("complaint")]
    return {"complaints": total, "counts": counts, "thin": total < MIN_COMPLAINTS, "other": dict(other.most_common(8)),
            "records": records, "labels": labels}


def _examples(comp, key):
    picked = []
    for label in sorted((l for l in comp["labels"] if l.get("theme") == key), key=lambda l: (-l["intensity"], l["id"])):
        record = comp["records"].get(label["id"])
        if record and store.verbatim(label.get("quote", ""), record["text"]):
            picked.append({"id": record["id"], "quote": label["quote"], "url": record["url"]})
        if len(picked) == EXAMPLES:
            break
    return picked


def _status(shares, tier, comps):
    """A thin competitor's shares never make a gap: 1 of 3 complaints is not a third of anything."""
    readable = {s: v for s, v in shares.items() if not comps[s]["thin"]}
    if any(v >= GAP_SHARE for v in readable.values()):
        if tier is None:
            return "unclear"  # no pain.json: we cannot say whether this pain is real for you
        return "open gap" if tier in LIVE_TIERS else "they struggle too"
    if all(v < SILENT_SHARE for v in shares.values()) and len(readable) == len(shares):
        return "maybe solved"
    return "unclear"


def build(folder):
    keys = _keys(_read_json(os.path.join(folder, "cluster_codebook.json")))
    codebook = {t["key"]: t for t in _read_json(os.path.join(folder, "cluster_codebook.json"))["themes"]}
    root = os.path.join(folder, "competitors")
    slugs = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))
                   and not d.startswith((".", "_"))) if os.path.isdir(root) else []
    if not slugs:
        raise ValueError("no competitor folders in %s yet. Mine and label each competitor first" % root)
    comps = {slug: _load_competitor(os.path.join(root, slug), slug, keys) for slug in slugs}
    pain_path = os.path.join(folder, "pain.json")
    pain = {t["key"]: t for t in _read_json(pain_path).get("themes", [])} if os.path.exists(pain_path) else {}
    rows = []
    for key in sorted(keys):
        shares = {s: round(c["counts"].get(key, 0) / c["complaints"], 4) if c["complaints"] else 0.0
                  for s, c in comps.items()}
        theme = pain.get(key, {})
        rows.append({"key": key, "name": theme.get("name") or codebook[key]["name"], "score": theme.get("score"),
                     "tier": theme.get("tier"), "shares": shares, "status": _status(shares, theme.get("tier"), comps),
                     "examples": {s: _examples(c, key) for s, c in comps.items()}})
    rows.sort(key=lambda r: (STATUS_ORDER.index(r["status"]), -(r["score"] or 0), r["key"]))
    return {"themes": rows, "competitors": {s: {k: c[k] for k in ("complaints", "thin", "other")}
                                            for s, c in comps.items()}}


def render(result):
    slugs = sorted(result["competitors"])
    lines = ["# Gap map", "",
             "Share of each competitor's own complaints that fall in each of your pain themes.", "",
             "| theme | your pain | %s | status |" % " | ".join(md(s) for s in slugs),
             "| --- | --- | %s | --- |" % " | ".join("---" for _ in slugs)]
    for r in result["themes"]:
        pain = "-" if r["score"] is None else ("%d %s" % (r["score"], r["tier"] or "")).strip()
        cells = " | ".join("%d%%" % round(r["shares"][s] * 100) for s in slugs)
        lines.append("| %s | %s | %s | %s |" % (md(r["name"]), pain, cells, r["status"]))
    lines += ["", "**open gap**: a pain you scored as real, and a tenth or more of a competitor's complaints are about it.",
              "**they struggle too**: competitors' users complain about it, but your data did not score it as real.",
              "**maybe solved**: under %d%% of every competitor's complaints, with at least %d complaints each." % (
                  round(SILENT_SHARE * 100), MIN_COMPLAINTS),
              "**unclear**: anything else, including when a competitor has too few complaints to read."]
    for r in [r for r in result["themes"] if r["status"] == "open gap"]:
        lines += ["", "## %s" % md(r["name"])]
        for slug in slugs:
            lines += ['> "%s" %s (%s)' % (md(e["quote"]), cite(e["id"], e["url"]), md(slug)) for e in r["examples"][slug]]
    lines += ["", "## What their users raise that your codebook does not cover", ""]
    for slug in slugs:
        comp = result["competitors"][slug]
        other = ", ".join("%s (%d)" % (md(k), v) for k, v in comp["other"].items()) or "nothing"
        lines.append("- %s, %d complaints%s: %s" % (md(slug), comp["complaints"], " (thin)" if comp["thin"] else "", other))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Map your pain themes against competitors' complaints")
    parser.add_argument("--dir", default=store.DEFAULT_DIR)
    args = parser.parse_args(argv)
    try:
        result = build(args.dir)
        with open(os.path.join(args.dir, "gaps.json"), "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=1)
        with open(os.path.join(args.dir, "gaps.md"), "w", encoding="utf-8") as fh:
            fh.write(render(result))
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 1
    for r in result["themes"]:
        print("%-18s %s" % (r["status"], r["name"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
