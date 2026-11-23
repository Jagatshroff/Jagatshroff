#!/usr/bin/env python3
"""The prospect list: people who described the pain in public, one row each.

  python3 prospects.py [--dir validator] [--theme KEY] [--community NAME] [--role ROLE]
                       [--sources reddit,hn,import] [--max 50] [--today YYYY-MM-DD]

Built only from mined, labelled complaints. Every quote is checked word for word
against the person's own post. Handles listed in validator/do_not_contact.txt
are always left out. Writes prospects.json and prospects.md. Contacts nobody.
"""

import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for sibling in ("validate-mine", "validate-pain", "validate-segment"):
    sys.path.insert(0, os.path.join(HERE, "..", sibling))

try:
    import store  # noqa: E402
    import signals  # noqa: E402
    from mdsafe import cite, link, md  # noqa: E402
    from segments import normalise_role  # noqa: E402
except ImportError:
    sys.exit("error: validate-prospects needs the rest of the pack next to it. Install the whole pack.")

DEFAULT_SOURCES = ("reddit", "hn", "import")  # app store reviewers cannot be reached
GONE = {"", "[deleted]", "[removed]", "deleted", "anonymous"}
STALE_DAYS = 548  # about 18 months: people rarely answer about a post that old
PROFILE = {
    "reddit": (re.compile(r"^[A-Za-z0-9_-]{3,20}$"), "https://www.reddit.com/user/%s"),
    "hn": (re.compile(r"^[A-Za-z0-9_-]{2,15}$"), "https://news.ycombinator.com/user?id=%s"),
}
DO_NOT_CONTACT = "do_not_contact.txt"
KNOWN_SOURCES = ("reddit", "hn", "import", "appstore")
is_bot = store.is_bot
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")


def handle_key(raw):
    """One spelling per person: '@Foo', 'u/foo', '/u/foo', a profile URL and 'foo' are all 'foo'."""
    text = str(raw or "").strip()
    text = re.split(r"\s+#", text)[0].strip()  # "foo  # asked on 3/4"
    found = re.search(r"[?&]id=([^&#\s]+)", text)
    if found:
        text = found.group(1)
    elif "://" in text:
        text = text.rstrip("/").rsplit("/", 1)[-1]
    text = re.sub(r"^/?u/", "", text)
    return text.lstrip("@").strip().lower()


def _do_not_contact(folder):
    path = os.path.join(folder, DO_NOT_CONTACT)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8-sig") as fh:  # Notepad and Excel add a byte-order mark
        return {handle_key(line) for line in fh if line.strip() and not line.lstrip().startswith("#")} - {""}


def _hide_contact_details(text):
    return _PHONE.sub("(phone hidden)", _EMAIL.sub("(email hidden)", text))


def _clean(label):
    """A hand-edited label with odd values is skipped, never fatal."""
    if type(label.get("intensity")) is not int or not isinstance(label.get("theme"), str) \
            or not isinstance(label.get("quote", ""), str):
        return None
    return label


def _profile(source, handle):
    rule = PROFILE.get(source)
    return rule[1] % handle if rule and rule[0].match(handle) else None


def _items(folder, theme, community, role):
    labels_path = os.path.join(folder, "labels.jsonl")
    if not os.path.exists(labels_path):
        raise ValueError("labels.jsonl not found. Run /validate-cluster first")
    records = {r["id"]: r for r in store.load(os.path.join(folder, store.FILE))}
    want_role = normalise_role(role) if role else None
    for label in store.load(labels_path):
        record = records.get(label.get("id"))
        if not record or not label.get("complaint"):
            continue
        if not _clean(label):
            yield record, None
            continue
        if theme and label.get("theme") != theme:
            continue
        if community and (record.get("community") or "").lower() != community.lower():
            continue
        if want_role and normalise_role(label.get("who")) != want_role:
            continue
        yield record, label


def _person(handle, rows, today):
    """rows: (record, label, signals) for one person. Picks their best verified quote."""
    ranked = sorted(rows, key=lambda x: x[0]["created"], reverse=True)  # newest first, kept on ties below
    ranked = sorted(ranked, key=lambda x: (not x[2]["money"], -x[1]["intensity"]))
    best = next(((r, l) for r, l, _ in ranked if store.verbatim(l.get("quote", ""), r["text"])), None)
    if not best:
        return None
    record, label = best
    latest = max(r["created"] for r, _, _ in rows)
    money_words = []
    for _, _, found in ranked:
        for kind in signals.MONEY:
            if found[kind] and found[kind] not in money_words:
                money_words.append(found[kind])
    roles = [normalise_role(l.get("who")) for _, l, _ in rows if normalise_role(l.get("who"))]
    return {
        "handle": handle, "source": record["source"], "profile": _profile(record["source"], handle),
        "who": roles[0] if roles else "", "complaints": len(rows),
        "themes": sorted({l["theme"] for _, l, _ in rows}), "money": any(s["money"] for _, _, s in rows), "money_words": money_words,
        "workaround": any(s["workaround"] for _, _, s in rows), "intensity": max(l["intensity"] for _, l, _ in rows),
        "communities": sorted({r.get("community") or "-" for r, _, _ in rows}), "latest": latest,
        "stale": (today - datetime.date.fromisoformat(latest)).days > STALE_DAYS,
        "quote": label["quote"], "post_id": record["id"], "post_url": record["url"],
    }


def build(folder, today, theme=None, community=None, role=None, sources=DEFAULT_SOURCES, limit=50):
    today = datetime.date.fromisoformat(today)
    sources = tuple(s.strip().lower() for s in sources)
    unknown = [s for s in sources if s not in KNOWN_SOURCES]
    if unknown:
        raise ValueError("unknown source(s) %s: use %s" % (", ".join(unknown), ", ".join(KNOWN_SOURCES)))
    blocked = _do_not_contact(folder)
    groups, shown, skipped = {}, {}, {"no_handle": 0, "bot": set(), "source": set(), "do_not_contact": set(),
                                      "no_verified_quote": 0, "bad_label": 0}
    for record, label in _items(folder, theme, community, role):
        if label is None:
            skipped["bad_label"] += 1
            continue
        handle = (record.get("author") or "").strip()
        key = handle_key(handle)
        if handle.lower() in GONE or not key:
            skipped["no_handle"] += 1
            continue
        if record["source"] not in sources:
            skipped["source"].add(key)
            continue
        if is_bot(handle):
            skipped["bot"].add(key)
            continue
        if key in blocked:
            skipped["do_not_contact"].add(key)
            continue
        shown.setdefault((record["source"], key), handle.lstrip("@"))
        groups.setdefault((record["source"], key), []).append((record, label, signals.detect(record["text"])))
    people = []
    for group, rows in groups.items():
        person = _person(shown[group], rows, today)
        if person:
            people.append(person)
        else:
            skipped["no_verified_quote"] += 1
    people.sort(key=lambda p: (not p["money"], -p["intensity"], -p["complaints"], p["stale"], p["handle"].lower()))
    total = len(people)
    return {"today": today.isoformat(), "filter": {"theme": theme, "community": community, "role": role,
                                                   "sources": list(sources)},
            "people": people[:limit], "found": total,
            "skipped": {k: len(v) if isinstance(v, set) else v for k, v in skipped.items()}}


def render(result):
    s = result["skipped"]
    lines = ["# Prospects", "",
             "%d people described the pain in public; showing %d. Left out: %d posts with no reachable author, "
             "%d bots, %d people from other sources, %d on the do-not-contact list, %d with no verified quote." % (
                 result["found"], len(result["people"]), s["no_handle"], s["bot"], s["source"], s["do_not_contact"],
                 s["no_verified_quote"]),
             "", "| # | person | where | role | money | posts | latest | their words |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for n, p in enumerate(result["people"], 1):
        who = "[%s](%s)" % (md(p["handle"]), link(p["profile"])) if p["profile"] else md(p["handle"])
        lines.append('| %d | %s | %s | %s | %s | %d | %s%s | "%s" %s |' % (
            n, who, md(", ".join(p["communities"])), md(p["who"] or "-"),
            "yes: %s" % md(_hide_contact_details(", ".join(p["money_words"]))) if p["money"] else "-",
            p["complaints"], p["latest"], " (old)" if p["stale"] else "", md(_hide_contact_details(p["quote"])),
            cite(p["post_id"], p["post_url"])))
    lines += ["", "Never message anyone from this list without reading their post first, and never in bulk.",
              "Anyone who asks not to be contacted goes into `%s`, and is left out of every future list." % DO_NOT_CONTACT]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="List the people who described the pain")
    parser.add_argument("--dir", default=store.DEFAULT_DIR)
    parser.add_argument("--theme")
    parser.add_argument("--community")
    parser.add_argument("--role")
    parser.add_argument("--sources", default=",".join(DEFAULT_SOURCES))
    parser.add_argument("--max", type=int, default=50)
    parser.add_argument("--today", default=datetime.date.today().isoformat())
    args = parser.parse_args(argv)
    try:
        sources = tuple(s.strip() for s in args.sources.split(",") if s.strip())
        result = build(args.dir, args.today, args.theme, args.community, args.role, sources, max(1, args.max))
        with open(os.path.join(args.dir, "prospects.json"), "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=1)
        with open(os.path.join(args.dir, "prospects.md"), "w", encoding="utf-8") as fh:
            fh.write(render(result))
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 1
    print("%d prospects (%d shown), skipped: %s" % (result["found"], len(result["people"]), json.dumps(result["skipped"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
