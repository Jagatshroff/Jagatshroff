"""A small, complete validator/ folder for the verdict tests: every earlier skill's output."""

import json
import os
import tempfile

from _load import load

store = load("validate-mine", "store")

POSTS = [
    ("r1", "I'm paying $40/mo and it still drops my WhatsApp every single week", "it still drops my WhatsApp every single week"),
    ("r2", "Honestly I'd pay $20 a month for one inbox that never misses a client", "I'd pay $20 a month for one inbox"),
    ("r3", "I keep missing LinkedIn replies from candidates and lose placements", "I keep missing LinkedIn replies"),
    ("r4", "Too many apps to check, kind of annoying but I live with it", "kind of annoying but I live with it"),
]


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def make(evidence_pass=True, real_world=None, bar_moved=False):
    folder = tempfile.mkdtemp()
    records, labels = [], []
    for native, text, quote in POSTS:
        r = store.build_record(source="reddit", native_id=native, url="https://www.reddit.com/r/x/%s/" % native,
                               text=text, created="2026-10-01", author="u_" + native, community="recruiting")
        records.append(r)
        labels.append({"id": r["id"], "relevant": True, "complaint": True, "theme": "drops" if native == "r1" else "missed",
                       "new_theme": "", "who": "recruiter", "tried": [], "intensity": 2, "quote": quote})
    store.save(os.path.join(folder, "complaints.jsonl"), records)
    store.save(os.path.join(folder, "labels.jsonl"), labels)
    bar = {"evidence": {"min_complaints": 3 if evidence_pass else 100, "min_money_signals": 2, "max_age_months": 24},
           "real_world": ["200 waitlist signups from strangers", "10 paid, refundable preorders"]}
    write_json(os.path.join(folder, "idea.json"), {
        "idea": "One inbox for recruiters", "target": "Solo recruiters", "problem": "Replies get missed",
        "hypothesis": "Solo recruiters would pay $20 to $40 a month", "search": {"terms": ["x"]}, "bar": bar})
    history = [{"moved": "2026-10-20", "reason": "narrowed to recruiters", "from": bar, "locked_since": "2026-10-01"}]
    write_json(os.path.join(folder, "idea.lock"), {"locked": "2026-10-01", "digest": "x", "bar": bar,
                                                   "history": history if bar_moved else []})
    have = len(POSTS)
    write_json(os.path.join(folder, "pain.json"), {
        "today": "2026-10-26", "since": "2024-10-26",
        "themes": [{"key": "drops", "name": "Connections drop", "score": 66, "tier": "worth money",
                    "metrics": {"complaints": 12, "money": 4}},
                   {"key": "missed", "name": "Missed replies", "score": 48, "tier": "real, unproven",
                    "metrics": {"complaints": 20, "money": 2}}],
        "bar": {"complaints": {"need": bar["evidence"]["min_complaints"], "have": have,
                               "pass": have >= bar["evidence"]["min_complaints"]},
                "money_signals": {"need": 2, "have": 2, "pass": True}},
        "totals": {"in_window": have}})
    write_json(os.path.join(folder, "wtp.json"), {"counts": {"would_pay": 1, "pays": 1, "too_expensive": 0, "mention": 0},
                                                  "range": {"low": None, "high": None, "note": "too few"}})
    write_json(os.path.join(folder, "gaps.json"), {"themes": [{"key": "drops", "name": "Connections drop",
                                                               "status": "open gap", "shares": {"beeper": 0.6}}],
                                                   "competitors": {"beeper": {"complaints": 40}}})
    write_json(os.path.join(folder, "segments.json"), {"roles": [{"name": "recruiter", "complaints": 4, "money": 2}],
                                                       "communities": [], "totals": {"complaints": 4}})
    if real_world is not None:
        write_json(os.path.join(folder, "realworld.json"), {"results": real_world})
    return folder, {r["native_id"]: r for r in records}
