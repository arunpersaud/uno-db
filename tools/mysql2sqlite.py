#!/usr/bin/env python3
"""Convert a uno-db mysqldump into a fresh SQLite database.

usage: mysql2sqlite.py DUMP.sql OUT.sqlite

The dump must be created with --skip-extended-insert (one INSERT per row).
OUT.sqlite must not exist yet; the schema comes from ../schema-sqlite.sql.
"""

import re
import sqlite3
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "schema-sqlite.sql"
INSERT = re.compile(r"^INSERT INTO `(\w+)` VALUES \((.*)\);$")
ESCAPES = {"0": "\0", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a",
           "b": "\b", "\\": "\\", "'": "'", '"': '"'}
ZERO_DATE = "0000-00-00 00:00:00"


def parse_values(s):
    """Parse the inside of a MySQL VALUES (...) tuple."""
    values, i, n = [], 0, len(s)
    while i < n:
        if s[i] == "'":
            i += 1
            buf = []
            while s[i] != "'" or s[i + 1:i + 2] == "'":
                if s[i] == "\\":
                    buf.append(ESCAPES.get(s[i + 1], s[i + 1]))
                    i += 2
                elif s[i] == "'":  # '' inside a string
                    buf.append("'")
                    i += 2
                else:
                    buf.append(s[i])
                    i += 1
            i += 1
            value = "".join(buf)
            values.append(None if value == ZERO_DATE else value)
        else:
            j = s.find(",", i)
            j = n if j == -1 else j
            token = s[i:j].strip()
            if token == "NULL":
                values.append(None)
            elif re.fullmatch(r"-?\d+", token):
                values.append(int(token))
            elif re.fullmatch(r"-?\d+\.\d*(e[-+]?\d+)?", token, re.I):
                values.append(float(token))
            else:
                raise ValueError(f"unsupported literal {token!r}")
            i = j
        if i < n:
            assert s[i] == ",", f"expected ',' at {i}: {s[i:i+20]!r}"
            i += 1
    return values


def main(dump, out):
    if Path(out).exists():
        sys.exit(f"{out} exists; refusing to overwrite")
    db = sqlite3.connect(out)
    db.executescript(SCHEMA.read_text())
    counts = {}
    with open(dump, encoding="utf-8") as f:
        for line in f:
            m = INSERT.match(line.rstrip("\n"))
            if not m:
                continue
            table, raw = m.groups()
            if table == "version" and counts.get("version"):
                continue  # the MySQL table had the same row 4 times
            values = parse_values(raw)
            marks = ",".join("?" * len(values))
            db.execute(f"INSERT INTO {table} VALUES ({marks})", values)
            counts[table] = counts.get(table, 0) + 1
    db.commit()
    for table, count in sorted(counts.items()):
        print(f"{table:12} {count:6}")
    db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
