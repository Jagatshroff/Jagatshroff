#!/usr/bin/env python3
"""Label mined complaints with sub-agents, in batches, against one shared codebook.

  python3 batches.py plan  [--batch 50] [--fresh | --only-other | --add-new]
  python3 batches.py check
  python3 batches.py save  b001 < reply.txt
  python3 batches.py tally [--allow-missing]

Global flag first: --dir validator. Reads validator/complaints.jsonl and
validator/cluster_codebook.json. Works in validator/cluster/. Writes
validator/themes.json and validator/labels.jsonl.
"""

import argparse
import collections
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "validate-mine"))

sys.path.insert(0, HERE)

try:
    import store  # noqa: E402
    from clusterbrief import BRIEF_TEXT, QUOTE_MAX, idea_line, write_batch  # noqa: E402,F401
except ImportError:
    sys.exit("error: validate-cluster needs the validate-mine folder next to it. Install the whole pack.")

CODEBOOK = "cluster_codebook.json"
WORK = "cluster"
THEMES = "themes.json"
LABELS = "labels.jsonl"
WAVE = 10
MIN_THEMES, MAX_THEMES = 2, 15
KEY = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FIELDS = ("id", "relevant", "complaint", "theme", "new_theme", "who", "tried", "intensity", "quote")

# Codebook ---------------------------------------------------------------

def codebook_problems(book):
    if not isinstance(book, dict) or not isinstance(book.get("themes"), list):
        return ["codebook must be an object with a 'themes' list"]
    themes, out, seen = book["themes"], [], set()
    if not MIN_THEMES <= len(themes) <= MAX_THEMES:
        out.append("codebook needs at least %d and at most %d themes, has %d" % (MIN_THEMES, MAX_THEMES, len(themes)))
    for n, theme in enumerate(themes, 1):
        if not isinstance(theme, dict):
            out.append("theme #%d is not an object" % n)
            continue
        key = str(theme.get("key", ""))
        if not KEY.match(key) or key == "other":
            out.append("theme #%d: key %r must be lowercase-with-dashes and not 'other'" % (n, key))
        elif key in seen:
            out.append("theme #%d: key %r is used twice" % (n, key))
        seen.add(key)
        if not str(theme.get("name") or "").strip() or not str(theme.get("definition") or "").strip():
            out.append("theme #%d (%s): needs a name and a one-line definition" % (n, key))
    return out


def theme_keys(book):
    return {t["key"] for t in book["themes"]}


# Files ------------------------------------------------------------------

def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


class Paths:
    def __init__(self, folder):
        self.dir = os.path.abspath(folder)  # briefs go to sub-agents that start in another folder
        folder = self.dir
        self.work = os.path.join(folder, WORK)
        self.codebook = os.path.join(folder, CODEBOOK)

    def batch(self, name):
        return os.path.join(self.work, "batches", name + ".json")

    def brief(self, name):
        return os.path.join(self.work, "briefs", name + ".md")

    def labels(self, name):
        return os.path.join(self.work, "labels", name + ".json")

    def batch_names(self):
        folder = os.path.join(self.work, "batches")
        return sorted(f[:-5] for f in os.listdir(folder) if f.endswith(".json")) if os.path.isdir(folder) else []


# Plan -------------------------------------------------------------------

def _load_codebook(paths):
    if not os.path.exists(paths.codebook):
        raise ValueError("no %s yet. Write the codebook first (see the skill)" % CODEBOOK)
    book = _read_json(paths.codebook)
    found = codebook_problems(book)
    if found:
        raise ValueError("codebook problems:\n- " + "\n- ".join(found))
    return book


def batched_ids(paths):
    return {i["id"] for name in paths.batch_names() for i in _read_json(paths.batch(name))["items"]}


def _next_number(paths, prefix):
    return len([n for n in paths.batch_names() if n.startswith(prefix)])


def plan(paths, size, fresh=False, only_other=False, add_new=False):
    if fresh and (only_other or add_new):
        raise ValueError("--fresh starts over, so it cannot be combined with --only-other or --add-new")
    book = _load_codebook(paths)
    records = store.load(os.path.join(paths.dir, store.FILE))
    idea = idea_line(paths.dir)
    if only_other:
        labels = _read_merged(paths)
        records = [r for r in records if labels.get(r["id"], {}).get("theme") == "other"]
        prefix, start = "r", _next_number(paths, "r")
    elif add_new:
        done = batched_ids(paths)
        records = [r for r in records if r["id"] not in done]
        prefix, start = "n", _next_number(paths, "n")
    else:
        if paths.batch_names() and not fresh:
            raise ValueError("batches already exist in %s. Use --fresh to start over (labels are lost)" % paths.work)
        prefix, start = "b", 0
    if not records:
        raise ValueError("nothing to label")
    if fresh:  # only now, once we know there is something to label: never wipe work and then fail
        if os.path.isdir(paths.work):
            shutil.rmtree(paths.work)
        for stale in (THEMES, LABELS):
            if os.path.exists(os.path.join(paths.dir, stale)):
                os.remove(os.path.join(paths.dir, stale))
    os.makedirs(os.path.join(paths.work, "labels"), exist_ok=True)  # sub-agents write here
    names = []
    for offset in range(0, len(records), size):
        name = "%s%03d" % (prefix, start + offset // size + 1)
        write_batch(paths, name, records[offset:offset + size], book, idea)
        names.append(name)
    return names


# Check and save -----------------------------------------------------------

def _is_int(value):
    return type(value) is int  # bool is an int subclass; True must not pass for 1


def _label_issue(label, text, keys):
    missing = [f for f in FIELDS if f not in label]
    if missing:
        return "missing field(s): %s" % ", ".join(missing)
    if not isinstance(label["relevant"], bool) or not isinstance(label["complaint"], bool):
        return "relevant and complaint must be true or false"
    if not isinstance(label["who"], str) or not isinstance(label["new_theme"], str):
        return "who and new_theme must be strings"
    if not isinstance(label["tried"], list) or not all(isinstance(x, str) for x in label["tried"]):
        return "tried must be a list of strings"
    if not label["complaint"]:
        return None if label["intensity"] == 0 and _is_int(label["intensity"]) else "intensity must be 0 when complaint is false"
    if not label["relevant"]:
        return "a complaint must also be relevant"
    theme = label.get("theme")
    if theme != "other" and theme not in keys:
        return "unknown theme %r" % theme
    if theme == "other" and not str(label.get("new_theme") or "").strip():
        return "theme is other, so new_theme needs a name"
    if not _is_int(label["intensity"]) or label["intensity"] not in (1, 2, 3):
        return "intensity must be 1, 2 or 3 for a complaint"
    quote = label.get("quote") or ""
    if len(quote) > QUOTE_MAX or not store.verbatim(quote, text):
        return "quote is not word for word from the post (or too long): %r" % quote[:80]
    return None


def label_problems(labels, records, keys):
    if not isinstance(labels, list):
        return ["labels must be a list"]
    texts = {r["id"]: r["text"] for r in records}
    out, seen = [], set()
    for n, label in enumerate(labels, 1):
        cid = label.get("id") if isinstance(label, dict) else None
        if cid not in texts:
            out.append("label #%d: unknown id %r" % (n, cid))
            continue
        if cid in seen:
            out.append("%s: appears twice" % cid)
            continue
        seen.add(cid)
        issue = _label_issue(label, texts[cid], keys)
        if issue:
            out.append("%s: %s" % (cid, issue))
    missing = [cid for cid in texts if cid not in seen]
    if missing:
        out.append("missing labels for %d post(s): %s" % (len(missing), ", ".join(missing[:5])))
    return out


def _batch_records(paths, name, by_id):
    """The batch's posts. A post removed from the store since planning is checked against
    the copy in the batch file, so a shrinking store never breaks a finished batch."""
    return [by_id.get(i["id"]) or {"id": i["id"], "text": i["text"]} for i in _read_json(paths.batch(name))["items"]]


def batch_status(paths, keys, by_id):
    """{batch: [problems]}; an empty list means the batch is done."""
    status = {}
    for name in paths.batch_names():
        if not os.path.exists(paths.labels(name)):
            status[name] = ["no labels yet"]
            continue
        try:
            labels = _read_json(paths.labels(name)).get("labels")
        except (ValueError, AttributeError):
            status[name] = ["labels file is not valid JSON"]
            continue
        status[name] = label_problems(labels, _batch_records(paths, name, by_id), keys)
    return status


def parse_reply(text):
    """Pull the labels out of a sub-agent's reply: fenced or bare JSON, list or object."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = fenced.group(1) if fenced else text
    starts = [i for i in (body.find("["), body.find("{")) if i >= 0]
    if not starts:
        raise ValueError("no JSON found in the reply")
    start = min(starts)
    end = max(body.rfind("]"), body.rfind("}")) + 1
    data = json.loads(body[start:end])
    return data.get("labels") if isinstance(data, dict) else data


# Tally ------------------------------------------------------------------

def _read_merged(paths):
    path = os.path.join(paths.dir, LABELS)
    if not os.path.exists(path):
        raise ValueError("no %s yet. Run tally first" % LABELS)
    with open(path, encoding="utf-8") as fh:
        return {row["id"]: row for row in (json.loads(line) for line in fh if line.strip())}


def _top(counter, n=10):
    return dict(counter.most_common(n))


def tally(paths, allow_missing=False):
    book = _load_codebook(paths)
    records = store.load(os.path.join(paths.dir, store.FILE))
    by_id = {r["id"]: r for r in records}
    status = batch_status(paths, theme_keys(book), by_id)
    broken = {name: p for name, p in status.items() if p}
    if broken and not allow_missing:
        raise ValueError("batches not finished: %s. Run check, or pass --allow-missing" % ", ".join(sorted(broken)))
    merged = {}
    for name in sorted(n for n in status if not status[n]):  # b, then n, then r: relabels win
        for label in _read_json(paths.labels(name))["labels"]:
            if label["id"] in by_id:  # posts removed from the store since planning drop out here
                merged[label["id"]] = {k: label[k] for k in FIELDS}
    complaints = [l for l in merged.values() if l["complaint"]]
    themes = []
    for t in book["themes"]:
        mine = [l for l in complaints if l["theme"] == t["key"]]
        themes.append(dict(t, count=len(mine), ids=[l["id"] for l in mine],
                           who=_top(collections.Counter(l["who"].strip().lower() for l in mine if l["who"].strip())),
                           tried=_top(collections.Counter(x.strip().lower() for l in mine for x in l["tried"] if str(x).strip())),
                           communities=_top(collections.Counter(by_id[l["id"]].get("community") or "-" for l in mine))))
    other = [{"id": l["id"], "new_theme": l["new_theme"]} for l in complaints if l["theme"] == "other"]
    result = {"codebook": book["themes"], "totals": {
        "in_store": len(records), "labeled": len(merged), "relevant": sum(1 for l in merged.values() if l["relevant"]),
        "complaints": len(complaints), "unlabeled": len(records) - len(merged), "other": len(other)},
        "themes": sorted(themes, key=lambda t: -t["count"]), "other": other}
    _write_json(os.path.join(paths.dir, THEMES), result)
    store.save(os.path.join(paths.dir, LABELS), [merged[k] for k in sorted(merged)])
    return result


# Command line -------------------------------------------------------------

def _print_waves(paths, names):
    for n in range(0, len(names), WAVE):
        wave = names[n:n + WAVE]
        print("wave %d: %s" % (n // WAVE + 1, " ".join(wave)))
        for name in wave:
            print("  %s" % paths.brief(name))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Label complaints in batches with sub-agents")
    parser.add_argument("--dir", default=store.DEFAULT_DIR)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--batch", type=int, default=50)
    p.add_argument("--fresh", action="store_true")
    p.add_argument("--only-other", action="store_true")
    p.add_argument("--add-new", action="store_true")
    sub.add_parser("check")
    sub.add_parser("save").add_argument("batch")
    sub.add_parser("tally").add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)
    paths = Paths(args.dir)
    try:
        if args.cmd == "plan":
            if args.batch < 1:
                raise ValueError("--batch must be at least 1")
            _print_waves(paths, plan(paths, args.batch, args.fresh, args.only_other, args.add_new))
            return 0
        if args.cmd == "tally":
            totals = tally(paths, args.allow_missing)["totals"]
            print(json.dumps(totals))
            return 0
        book = _load_codebook(paths)
        by_id = {r["id"]: r for r in store.load(os.path.join(paths.dir, store.FILE))}
        if args.cmd == "check":
            status = batch_status(paths, theme_keys(book), by_id)
            for name, found in sorted(status.items()):
                for problem in found[:8]:
                    print("%s: %s" % (name, problem))
            done = sum(1 for p in status.values() if not p)
            print("%d of %d batches done" % (done, len(status)))
            unbatched = len(set(by_id) - batched_ids(paths))
            if unbatched:
                print("%d complaint%s in the store %s in no batch yet. Run plan --add-new to label them" % (
                    unbatched, "" if unbatched == 1 else "s", "is" if unbatched == 1 else "are"))
            return 0 if status and done == len(status) else 1
        if args.batch not in paths.batch_names():
            raise ValueError("no batch named %s" % args.batch)
        labels = parse_reply(sys.stdin.read())
        found = label_problems(labels, _batch_records(paths, args.batch, by_id), theme_keys(book))
        if found:
            raise ValueError("not saved:\n- " + "\n- ".join(found[:10]))
        _write_json(paths.labels(args.batch), {"batch": args.batch, "labels": labels})
        print("saved %s" % paths.labels(args.batch))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
