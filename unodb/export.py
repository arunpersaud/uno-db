"""CSV downloads of the tables on the stats pages."""

import csv
import io

from flask import Response

from .db import WINNER

# a spreadsheet would run cells starting with these as formulas
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def cell(value):
    if isinstance(value, str) and value.startswith(FORMULA_START):
        return "'" + value
    return value


def csv_response(filename: str, header: list[str], rows) -> Response:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    for row in rows:
        writer.writerow([cell(v) for v in row])
    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


SCORE_HEADER = [
    "date", "location", "game_type", "session", "game", "player", "seat",
    "points", "won", "black_card",
]  # fmt: skip


def score_rows(rows):
    """Long format: one row per player and game (from stats.all_scores)."""
    numbers = {}  # game id -> number of the game in its session
    per_session = {}  # session id -> games numbered so far
    for row in rows:
        if row["game"] not in numbers:
            per_session[row["session"]] = per_session.get(row["session"], 0) + 1
            numbers[row["game"]] = per_session[row["session"]]
        game_nr = numbers[row["game"]]
        yield [
            row["date"],
            row["location"],
            row["variation"],
            row["session"],
            game_nr,
            row["name"],
            row["position"] + 1,
            0 if row["score"] == WINNER else row["score"],
            int(row["score"] == WINNER),
            row["black"],
        ]
