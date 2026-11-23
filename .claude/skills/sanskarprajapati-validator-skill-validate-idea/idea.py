#!/usr/bin/env python3
"""Check validator/idea.json and lock its pass/fail bar.

  python3 idea.py check validator/idea.json
  python3 idea.py lock  validator/idea.json [--reason "why the bar moved"]

The bar is locked before any data comes in. check fails if it moved since.
Moving it on purpose needs --reason, and every move is kept in idea.lock so the
verdict can say so.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile

LOCK = "idea.lock"
LOCK_KEYS = ("locked", "digest", "bar", "history")
TEXT_FIELDS = ("idea", "target", "problem", "hypothesis")
EVIDENCE = {"min_complaints": 1, "min_money_signals": 0, "max_age_months": 1}  # field -> smallest allowed


def _text(data, key, out):
    if not isinstance(data.get(key), str) or not data[key].strip():
        out.append("%s: write it as one plain sentence" % key)


def _string_list(value, name, out, required):
    if value is None and not required:
        return
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        out.append("%s: must be a list of non-empty strings" % name)
    elif required and not value:
        out.append("%s: needs at least one entry" % name)


def _apps(apps, out):
    if apps is None:
        return
    if not isinstance(apps, list):
        out.append("search.competitor_apps: must be a list")
        return
    for n, app in enumerate(apps, 1):
        if not isinstance(app, dict) or not str(app.get("name") or "").strip():
            out.append("search.competitor_apps #%d: needs a name" % n)
        elif "app_store_id" in app and not re.match(r"^\d+$", str(app["app_store_id"])):
            out.append("search.competitor_apps #%d: app_store_id must be digits (find it with sources.py find-app)" % n)


def _bar(bar, out):
    if not isinstance(bar, dict):
        out.append("bar: missing. Set the pass/fail bar now, before any data comes in")
        return
    evidence = bar.get("evidence")
    if not isinstance(evidence, dict):
        out.append("bar.evidence: missing")
    else:
        for field, smallest in EVIDENCE.items():
            value = evidence.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < smallest:
                out.append("bar.evidence.%s: must be a whole number, at least %d" % (field, smallest))
    _string_list(bar.get("real_world"), "bar.real_world", out, required=True)


def problems(data):
    """Every problem with an idea.json, all at once. An empty list means it is valid."""
    if not isinstance(data, dict):
        return ["idea.json must be a JSON object"]
    out = []
    for key in TEXT_FIELDS:
        _text(data, key, out)
    search = data.get("search")
    if not isinstance(search, dict):
        out.append("search: missing")
    else:
        _string_list(search.get("terms"), "search.terms", out, required=True)
        _string_list(search.get("subreddits"), "search.subreddits", out, required=False)
        _apps(search.get("competitor_apps"), out)
    _bar(data.get("bar"), out)
    return out


def bar_digest(bar):
    return hashlib.sha256(json.dumps(bar, sort_keys=True).encode("utf-8")).hexdigest()


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _lock_path(path):
    return os.path.join(os.path.dirname(os.path.abspath(path)), LOCK)


def _read_lock(lock_path):
    """The lock, or None if there is none. A damaged lock is an error, never a pass."""
    if not os.path.exists(lock_path):
        return None
    try:
        lock = _read(lock_path)
    except ValueError:
        lock = None
    if not isinstance(lock, dict) or any(k not in lock for k in LOCK_KEYS):
        raise LockError("%s is damaged. Restore it from git, or delete it and lock again (the move will "
                        "show up as a lock with no history)" % LOCK)
    return lock


class LockError(Exception):
    pass


def _today():
    return datetime.date.today().isoformat()


def check(path):
    """Returns (problems, locked)."""
    data = _read(path)
    found = problems(data)
    lock = _read_lock(_lock_path(path))
    if not found and lock and bar_digest(data["bar"]) != lock["digest"]:
        found.append("bar: changed since it was locked on %s. Put it back, or run lock with --reason"
                     % lock["locked"])
    return found, lock is not None


def lock(path, reason=None):
    data = _read(path)
    found = problems(data)
    if found:
        return found
    lock_path = _lock_path(path)
    digest = bar_digest(data["bar"])
    entry = {"locked": _today(), "digest": digest, "bar": data["bar"], "history": []}
    old = _read_lock(lock_path)
    if old:
        if old["digest"] == digest:
            return []
        if not reason:
            return ["bar: already locked on %s with different numbers. Moving it needs --reason" % old["locked"]]
        entry["history"] = old.get("history", []) + [
            {"moved": _today(), "reason": reason, "from": old["bar"], "locked_since": old["locked"]}]
    handle, tmp = tempfile.mkstemp(dir=os.path.dirname(lock_path), suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as fh:
        json.dump(entry, fh, indent=2)
    os.chmod(tmp, 0o644)
    os.replace(tmp, lock_path)
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check idea.json and lock the pass/fail bar")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").add_argument("path")
    p = sub.add_parser("lock")
    p.add_argument("path")
    p.add_argument("--reason")
    args = parser.parse_args(argv)
    locked = True
    try:
        if args.cmd == "check":
            found, locked = check(args.path)
        else:
            found = lock(args.path, args.reason)
    except LockError as err:
        print("error: %s" % err, file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("error: %s not found" % args.path, file=sys.stderr)
        return 1
    except ValueError as err:
        print("error: %s is not valid JSON: %s" % (args.path, err), file=sys.stderr)
        return 1
    if found:
        for problem in found:
            print("- " + problem, file=sys.stderr)
        return 1
    if args.cmd == "lock":
        print("ok: bar locked")
    elif locked:
        print("ok: valid, bar unchanged since it was locked")
    else:
        print("ok: valid, but the bar is not locked yet. Run lock once the user agrees to it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
