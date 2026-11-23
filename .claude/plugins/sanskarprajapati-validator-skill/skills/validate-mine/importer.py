"""Read complaints the user pasted or exported: .txt, .md, .csv, .json or .jsonl."""

import csv
import datetime
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import store  # noqa: E402

META = re.compile(r"^(url|author|date|title):\s*(.+)$", re.I)
ENCODING = "utf-8-sig"  # Excel and some editors start files with a byte-order mark


def _field(row, key):
    """A text field as a clean string. Numbers are fine; lists and objects are dropped."""
    value = row.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return value.strip() if isinstance(value, str) else ""


def _score(value):
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def read_import(path, name, today=None):
    """Return (records, skipped) from a file. name says where it came from (x, g2, survey...).

    A bad row is skipped with a message naming its row number; it never sinks the file.
    """
    today = today or datetime.date.today().isoformat()
    ext = os.path.splitext(path)[1].lower()
    readers = {".txt": _txt_rows, ".md": _txt_rows, ".csv": _csv_rows, ".json": _json_rows, ".jsonl": _jsonl_rows}
    if ext not in readers:
        raise ValueError("unsupported extension %r: use .txt, .md, .csv, .json or .jsonl" % ext)
    base = os.path.basename(path)
    records, skipped = [], []
    for number, row in enumerate(readers[ext](path), 1):
        text = _field(row, "text")
        if not text:
            continue
        try:
            records.append(store.build_record(
                source="import",
                native_id=hashlib.sha1(text.encode("utf-8")).hexdigest(),
                url=_field(row, "url") or "%s#%d" % (base, number),
                text=text,
                created=_field(row, "date") or today,
                author=_field(row, "author"),
                title=_field(row, "title"),
                score=_score(row.get("score")),
                community=name,
                kind="import",
            ))
        except ValueError as err:
            skipped.append("%s row %d: %s" % (base, number, err))
    return records, skipped


def _txt_rows(path):
    with open(path, encoding=ENCODING) as fh:
        text = fh.read()
    if re.search(r"^---\s*$", text, re.M):
        blocks = re.split(r"^---\s*$", text, flags=re.M)
    else:
        blocks = re.split(r"\n\s*\n", text)
    rows = []
    for block in blocks:
        lines, row = block.strip().split("\n"), {}
        while lines and META.match(lines[0].strip()):
            key, value = META.match(lines[0].strip()).groups()
            row[key.lower()] = value
            lines = lines[1:]
        row["text"] = "\n".join(lines).strip()
        if row["text"]:
            rows.append(row)
    return rows


def _lower_keys(row):
    return {str(k).strip().lower(): v for k, v in row.items() if k is not None}


def _csv_rows(path):
    with open(path, encoding=ENCODING, newline="") as fh:
        reader = csv.DictReader(fh)
        if "text" not in [f.strip().lower() for f in (reader.fieldnames or [])]:
            raise ValueError("%s needs a 'text' column" % os.path.basename(path))
        try:
            return [_lower_keys(row) for row in reader]
        except csv.Error as err:
            raise ValueError("%s line %d: %s" % (os.path.basename(path), reader.line_num, err))


def _json_rows(path):
    with open(path, encoding=ENCODING) as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("%s must hold a JSON list of objects" % os.path.basename(path))
    return [_lower_keys(row) for row in data if isinstance(row, dict)]


def _jsonl_rows(path):
    rows = []
    with open(path, encoding=ENCODING) as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                raise ValueError("%s line %d is not valid JSON" % (os.path.basename(path), number))
            if isinstance(row, dict):
                rows.append(_lower_keys(row))
    return rows
