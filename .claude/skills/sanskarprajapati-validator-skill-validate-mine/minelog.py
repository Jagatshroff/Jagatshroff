"""The mining run log (validator/mine_log.jsonl) and the coverage report (validator/sources.md)."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import store  # noqa: E402

LOG = "mine_log.jsonl"
REPORT = "sources.md"
KNOWN = ("reddit", "hn", "appstore", "import")


def append_log(folder, entry):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, LOG), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_log(folder):
    path = os.path.join(folder, LOG)
    if not os.path.exists(path):
        return []
    runs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                runs.append(json.loads(line))
            except ValueError:
                continue  # a run cut off mid-write; the store itself is unaffected
    return runs


def write_report(folder):
    records = store.load(os.path.join(folder, store.FILE))
    summary = store.stats(records)
    lines = ["# Sources", "",
             "%d complaints, from %s to %s." % (summary["total"], summary["first"] or "-", summary["last"] or "-"), "",
             "| source | complaints | first | last |", "| --- | --- | --- | --- |"]
    for source in KNOWN:
        dates = sorted(r["created"] for r in records if r["source"] == source)
        lines.append("| %s | %d | %s | %s |" % (source, len(dates), dates[0] if dates else "-", dates[-1] if dates else "-"))
    missing = [s for s in KNOWN if s not in summary["by_source"]]
    if missing:
        lines += ["", "Not covered yet: %s." % ", ".join(missing)]
    lines += ["", "## Runs", "", "| when | source | target | fetched | matched | added | duplicates | error |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for run in _read_log(folder):
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            str(run.get("at", "?"))[:16], run.get("source", "?"), str(run.get("target", "")).replace("|", "/"),
            run.get("raw", "-"),
            run.get("matched", "-"), run.get("added", "-"), run.get("dupes", "-"), run.get("error") or ""))
    lines += ["", "X has no free API, so X posts only arrive through `import`. Reddit comes from the",
              "PullPush archive, which can lag behind reddit.com by a week or two. Check the newest date above."]
    with open(os.path.join(folder, REPORT), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return summary
