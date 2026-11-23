"""links.md: every link the run found, grouped by pain theme, then the rest. Used by report.py.

Each complaint carries its verified quote, so the file is checked like every
other report. No author names: a link and a few words are enough to find a post.
"""

import os

import store
from mdsafe import cite, md
from trialpack import read_json

OTHER = "other"


def _theme_names(folder):
    """Theme key -> name, best-scoring first (pain.json), then any others from the codebook."""
    names = {}
    for t in (read_json(os.path.join(folder, "pain.json"), {}) or {}).get("themes", []):
        names[t["key"]] = t["name"]
    for t in (read_json(os.path.join(folder, "themes.json"), {}) or {}).get("codebook", []):
        names.setdefault(t["key"], t["name"])
    names.setdefault(OTHER, "Other (no theme yet)")
    return names


def _line(record, quote=None):
    where = "%s, %s, %s" % (md(record["source"]), md(record.get("community") or "-"), record["created"])
    words = ' "%s"' % md(quote) if quote and store.verbatim(quote, record["text"]) else ""
    return "- %s %s%s" % (cite(record["id"], record["url"]), where, words)


def _sections(records, labels, names, heading=lambda name: name):
    groups = {key: [] for key in names}
    relevant, noise, unlabelled = [], [], []
    for record in records:
        label = labels.get(record["id"])
        if label is None:
            unlabelled.append(record)
        elif label.get("complaint"):
            groups.setdefault(label.get("theme") or OTHER, []).append((record, label.get("quote")))
        elif label.get("relevant"):
            relevant.append(record)
        else:
            noise.append(record)
    lines = []
    for key, rows in groups.items():
        if rows:
            lines += ["", "## %s (%d)" % (md(heading(names.get(key, key))), len(rows)), ""]  # names are model-written
            lines += [_line(r, q) for r, q in sorted(rows, key=lambda x: x[0]["created"], reverse=True)]
    for title, rows in (("Relevant, not complaints", relevant), ("Not relevant", noise), ("Not labelled", unlabelled)):
        if rows:
            lines += ["", "## %s (%d)" % (md(heading(title)), len(rows)), ""]
            lines += [_line(r) for r in sorted(rows, key=lambda r: r["created"], reverse=True)]
    return lines


def _labels(path):
    return {l["id"]: l for l in store.load(path)} if os.path.exists(path) else {}


def render_links(folder):
    names = _theme_names(folder)
    records = store.load(os.path.join(folder, store.FILE))
    lines = ["# Every link the run found", "",
             "Grouped by pain theme (highest score first), then relevant posts that were not complaints, then",
             "posts that only shared the search words. Each complaint shows its quote, checked against the post."]
    lines += _sections(records, _labels(os.path.join(folder, "labels.jsonl")), names)
    root = os.path.join(folder, "competitors")
    if os.path.isdir(root):
        for slug in sorted(d for d in os.listdir(root) if not d.startswith((".", "_"))):
            sub = os.path.join(root, slug)
            comp = store.load(os.path.join(sub, store.FILE))
            if not comp:
                continue
            lines += ["", "## Competitor: %s (%d)" % (md(slug), len(comp))]
            lines += [line.replace("## ", "### ", 1) if line.startswith("## ") else line
                      for line in _sections(comp, _labels(os.path.join(sub, "labels.jsonl")), names)]
    return "\n".join(lines) + "\n"
