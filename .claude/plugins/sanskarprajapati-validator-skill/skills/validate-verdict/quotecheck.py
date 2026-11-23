#!/usr/bin/env python3
"""Check every quote in every report against the post it cites.

  python3 quotecheck.py [--dir validator]

Reads every .md file in the state folder (not the cluster or trial work files).
A quoted line followed on the same line by a complaint ID (R/H/A/I + 8 hex) must
appear word for word in that complaint. Every cited ID must exist, in the main
store or in a competitor's. In report.md even a quote with no citation fails.
Exits 1 on any failure, so nothing false ships quietly.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "validate-mine"))

try:
    import store  # noqa: E402
except ImportError:
    sys.exit("error: validate-verdict needs the validate-mine folder next to it. Install the whole pack.")

SKIP_DIRS = {"cluster", "trial", "cache", "import", "interviews"}  # working files, not reports
ID = re.compile(r"\b[RHAI][0-9a-f]{8}\b")
# Straight, curly double, curly single and guillemet quotes all count as quoting.
QUOTE = re.compile('"([^"\n]{3,600})"'
                   "|“([^”\n]{3,600})”"
                   "|‘([^’\n]{3,600})’"
                   "|«([^»\n]{3,600})»")
HIDDEN = re.compile(r"\((?:email|phone) hidden\)")
MAX_HIDDEN = 40  # a hidden email or phone number stands for a few characters, never a paragraph
STRICT = ("report.md",)  # the report makes the strongest claims, so an uncited quote there fails
_ESCAPE = re.compile(r"\\([\\`*_\[\]<>|'\"])")


def _unescape(text):
    """Undo exactly what mdsafe.md() does, and nothing more, so we compare the words."""
    return _ESCAPE.sub(r"\1", text).replace("&#58;", ":").replace("&#46;", ".")


def _texts(folder):
    texts = {}
    paths = [os.path.join(folder, store.FILE)]
    comp_root = os.path.join(folder, "competitors")
    if os.path.isdir(comp_root):
        paths += [os.path.join(comp_root, d, store.FILE) for d in sorted(os.listdir(comp_root))]
    for path in paths:
        for record in store.load(path):
            texts[record["id"]] = record.get("text") or ""
    return texts


def quote_matches(quote, text):
    """Word for word, where '(email hidden)' and '(phone hidden)' may stand for a short run of text."""
    if not isinstance(quote, str):
        return False
    if not HIDDEN.search(quote):
        return store.verbatim(quote, text)
    pieces = [p for p in (store._squash(p).strip(" ,.;:") for p in HIDDEN.split(quote)) if p]
    if len(" ".join(pieces).split()) < store.MIN_QUOTE_WORDS:
        return False
    gap = "[^\n]{1,%d}?" % MAX_HIDDEN
    pattern = re.compile(gap.join(re.escape(p) for p in pieces))
    haystack, edges = store._squash(text), pieces[0][0] + pieces[-1][-1]
    return any(store._edge_ok(haystack, m.start(), m.end(), edges) for m in pattern.finditer(haystack))


def _md_files(folder):
    for base, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            if name.endswith(".md"):
                yield os.path.join(base, name)


def _quoted(match):
    return next(g for g in match.groups() if g is not None)


def _check_line(line, number, rel, texts, strict, result):
    for cid in ID.findall(line):
        if cid not in texts:
            result["unknown"].append({"file": rel, "line": number, "id": cid})
    for match in QUOTE.finditer(line):
        quote = _unescape(_quoted(match))
        if len(quote.split()) < store.MIN_QUOTE_WORDS:
            continue  # too short to be a citation, and verbatim() would refuse it anyway
        cited = ID.search(line, match.end())
        if not cited:
            result["uncited"] += 1
            if os.path.basename(rel) in strict:
                result["failed"].append({"file": rel, "line": number, "id": "-", "quote": quote[:120]})
            continue
        if cited.group(0) not in texts:
            continue  # already reported as unknown
        if quote_matches(quote, texts[cited.group(0)]):
            result["ok"] += 1
        else:
            result["failed"].append({"file": rel, "line": number, "id": cited.group(0), "quote": quote[:120]})


def check_folder(folder, strict=STRICT):
    texts = _texts(folder)
    result = {"ok": 0, "failed": [], "unknown": [], "uncited": 0, "files": 0}
    for path in _md_files(folder):
        result["files"] += 1
        rel = os.path.relpath(path, folder)
        with open(path, encoding="utf-8") as fh:
            for number, line in enumerate(fh.read().split("\n"), 1):
                _check_line(line, number, rel, texts, strict, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check every cited quote against its post")
    parser.add_argument("--dir", default=store.DEFAULT_DIR)
    args = parser.parse_args(argv)
    try:
        result = check_folder(args.dir)
    except (ValueError, OSError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 1
    print("%d quotes checked word for word in %d files, %d quoted lines with no citation." % (
        result["ok"], result["files"], result["uncited"]))
    for f in result["failed"]:
        print("NOT IN THE POST  %s:%d  %s  \"%s\"" % (f["file"], f["line"], f["id"], f["quote"]))
    for u in result["unknown"]:
        print("UNKNOWN ID       %s:%d  %s" % (u["file"], u["line"], u["id"]))
    return 1 if result["failed"] or result["unknown"] else 0


if __name__ == "__main__":
    sys.exit(main())
