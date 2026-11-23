#!/usr/bin/env python3
"""The complaint store: validator/complaints.jsonl.

One JSON object per line, one shape for every source. Every complaint gets a
stable short ID (R/H/A/I + 8 hex) so later skills can cite it.

  python3 store.py stats  [--dir validator]
  python3 store.py show   ID [--dir validator]
  python3 store.py sample [--n 10] [--seed 1] [--dir validator]
"""

import argparse
import datetime
import hashlib
import html
import json
import os
import random
import re
import sys
import tempfile

PREFIX = {"reddit": "R", "hn": "H", "appstore": "A", "import": "I"}
REQUIRED = ("source", "native_id", "url", "text", "created")
OPTIONAL = {"author": "", "title": "", "score": None, "rating": None, "community": "", "kind": "",
            "query": "", "fetched": ""}
MAX_TEXT = 4000
NEAR_DUP = 0.85  # word-shingle Jaccard at or above this is the same complaint
SHINGLE = 5
DEFAULT_DIR = "validator"
FILE = "complaints.jsonl"

_TAG_BREAK = re.compile(r"<\s*(p|br|li|div)\b[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")
_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_WORD = re.compile(r"\w+")  # Unicode-aware: Chinese, Cyrillic and accents all count
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # keeps \t and \n


def clean_text(raw):
    """HTML and entities out, whitespace tidied, paragraph breaks kept."""
    if not raw:
        return ""
    text = _TAG_BREAK.sub("\n", raw)
    text = _CONTROL.sub("", html.unescape(_TAG.sub("", text)))
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        lines = (" ".join(line.split()) for line in block.split("\n"))
        joined = "\n".join(line for line in lines if line)
        if joined:
            paragraphs.append(joined)
    return "\n\n".join(paragraphs)


_CURLY = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def _squash(text):
    return " ".join(text.translate(_CURLY).split())


KNOWN_BOTS = {"automoderator", "remindmebot", "savevideo", "repostsleuthbot", "sneakpeekbot", "wikitextbot"}


def is_bot(handle):
    """AutoModerator, RemindMeBot, sports_bot, Foo-Bot2. Not Abbott, Talbot or ROBOT:
    the 'bot' has to read as its own word."""
    handle = re.sub(r"\d+$", "", str(handle or ""))
    if handle.lower() in KNOWN_BOTS:
        return True
    if len(handle) <= 3 or not handle.lower().endswith("bot"):
        return False
    before = handle[-4]
    return before in "_-" or (handle[-3] == "B" and (before.islower() or before.isdigit()))


MIN_QUOTE_WORDS = 3


def _edge_ok(text, start, end, quote):
    """A quote may not begin or end in the middle of a word ("ill" out of "bill")."""
    if quote[0].isalnum() and start > 0 and text[start - 1].isalnum():
        return False
    return not (quote[-1].isalnum() and end < len(text) and text[end].isalnum())


def verbatim(quote, text):
    """Is quote really in text, word for word, and long enough to be evidence?
    Whitespace and curly quotes may differ, nothing else may. At least three
    words, starting and ending on word edges. This keeps every cited quote honest."""
    quote, text = _squash(quote or ""), _squash(text or "")
    if len(quote.split()) < MIN_QUOTE_WORDS:
        return False
    start = text.find(quote)
    while start >= 0:
        if _edge_ok(text, start, start + len(quote), quote):
            return True
        start = text.find(quote, start + 1)
    return False


def make_id(source, native_id):
    if source not in PREFIX:
        raise ValueError("unknown source %r, expected one of %s" % (source, ", ".join(sorted(PREFIX))))
    digest = hashlib.sha1(("%s:%s" % (source, native_id)).encode("utf-8")).hexdigest()
    return PREFIX[source] + digest[:8]


def _as_int(name, value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be a whole number, got %r" % (name, value))


def build_record(**fields):
    """Validate one complaint and return a new, normalised record."""
    unknown = set(fields) - set(REQUIRED) - set(OPTIONAL)
    if unknown:
        raise ValueError("unknown field(s): %s" % ", ".join(sorted(unknown)))
    for name in REQUIRED:
        if not str(fields.get(name) or "").strip():
            raise ValueError("missing required field: %s" % name)
    match = _DATE.match(str(fields["created"]))
    try:
        datetime.date.fromisoformat(match.group(1) if match else "")
    except ValueError:
        raise ValueError("created must start with a real YYYY-MM-DD date, got %r" % fields["created"])
    text = clean_text(fields["text"])
    if not text:
        raise ValueError("text is empty after cleaning")
    record = dict(OPTIONAL)
    record.update({k: v for k, v in fields.items() if k in OPTIONAL and v is not None})
    record.update(
        id=make_id(fields["source"], fields["native_id"]),
        source=fields["source"],
        native_id=str(fields["native_id"]),
        url=str(fields["url"]).strip(),
        created=match.group(1),
        text=text[:MAX_TEXT],
        truncated=len(text) > MAX_TEXT,
        title=clean_text(fields.get("title")),
        score=_as_int("score", fields.get("score")),
        rating=_as_int("rating", fields.get("rating")),
    )
    return record


def _normal(text):
    return " ".join(_WORD.findall(text.lower()))


def _shingles(normal):
    words = normal.split()
    if len(words) <= SHINGLE:
        return None
    return frozenset(tuple(words[i:i + SHINGLE]) for i in range(len(words) - SHINGLE + 1))


def _is_near(a, b):
    small, big = sorted((len(a), len(b)))
    if small / big < NEAR_DUP:  # Jaccard cannot reach the bar
        return False
    return len(a & b) / len(a | b) >= NEAR_DUP


def _exact_key(record, normal):
    """Long texts match on words alone. Short ones ("Too expensive.") are said by many
    different people, so they only match when the same named author said them."""
    if not normal:
        return None
    if len(normal.split()) > SHINGLE:
        return ("", normal)
    author = (record.get("author") or "").strip().lower()
    return (record.get("source"), author, normal) if author else None


class _Index:
    def __init__(self, records):
        self.ids, self.exact, self.sets = set(), set(), []
        for r in records:
            self.add(r)

    def add(self, record):
        normal = _normal(record.get("text") or "")
        self.ids.add(record["id"])
        key = _exact_key(record, normal)
        if key:
            self.exact.add(key)
        sh = _shingles(normal)
        if sh:
            self.sets.append(sh)

    def seen(self, record):
        if record["id"] in self.ids:
            return True
        normal = _normal(record.get("text") or "")
        key = _exact_key(record, normal)
        if key and key in self.exact:
            return True
        sh = _shingles(normal)
        return bool(sh) and any(_is_near(sh, other) for other in self.sets)


def merge(existing, incoming):
    """Return (merged, added, duplicates). Neither input list is changed."""
    index = _Index(existing)
    merged, added, dupes = list(existing), 0, 0
    for record in incoming:
        if index.seen(record):
            dupes += 1
            continue
        merged.append(dict(record))
        index.add(record)
        added += 1
    return merged, added, dupes


def load(path):
    if not os.path.exists(path):
        return []
    records = []
    with open(path, encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as err:
                raise ValueError("%s line %d is not valid JSON: %s" % (path, number, err.msg))
    return records


def save(path, records):
    """Write atomically: a crash never leaves half a file behind."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    os.chmod(tmp, 0o644)  # mkstemp makes 0600; the store is not a secret
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def add(path, records):
    """Merge records into the file at path. Returns (added, duplicates)."""
    merged, added, dupes = merge(load(path), records)
    if added:
        save(path, merged)
    return added, dupes


def stats(records):
    by_source = {}
    for r in records:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    dates = sorted(r["created"] for r in records)
    return {"total": len(records), "by_source": dict(sorted(by_source.items())),
            "first": dates[0] if dates else None, "last": dates[-1] if dates else None}


def _main(argv=None):
    parser = argparse.ArgumentParser(description="The Validator complaint store")
    parser.add_argument("--dir", default=DEFAULT_DIR)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats")
    show = sub.add_parser("show")
    show.add_argument("id")
    sample = sub.add_parser("sample")
    sample.add_argument("--n", type=int, default=10)
    sample.add_argument("--seed", type=int, default=1)
    args = parser.parse_args(argv)

    try:
        records = load(os.path.join(args.dir, FILE))
    except ValueError as err:
        print("error: %s" % err, file=sys.stderr)
        return 1
    if args.cmd == "stats":
        print(json.dumps(stats(records), indent=2))
    elif args.cmd == "show":
        found = [r for r in records if r["id"] == args.id]
        if not found:
            print("error: no complaint with id %s" % args.id, file=sys.stderr)
            return 1
        print(json.dumps(found[0], indent=2, ensure_ascii=False))
    else:
        picked = random.Random(args.seed).sample(records, min(args.n, len(records)))
        for r in picked:
            print("[%s] %s %s\n  %s\n" % (r["id"], r["created"], r["url"], r["text"][:280].replace("\n", " ")))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
