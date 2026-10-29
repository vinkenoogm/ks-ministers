"""Read-only export of the submissions table used by app.py (Python 3.11+)."""

import csv
from pathlib import Path
import sys
import tomllib

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


PROJECT_DIR = Path(__file__).resolve().parent
COLUMNS = [
    "submission_id", "created_at", "username", "alliance", "username_alliance",
    "in_game_id", "appointment_day", "appointment_date", "minister",
    "selected_times", "available_slots_utc", "speedups_days", "tg", "ttg",
    "dust", "comments",
]


def flatten_submission(submission):
    payload = submission["payload"]
    identity = payload.get("username_alliance", submission["username_alliance"])
    username, separator, alliance = identity.rpartition(" [")
    if not separator or not alliance.endswith("]"):
        username, alliance = identity, ""
    else:
        alliance = alliance[:-1]
    days = payload.get("days", {})
    for day in ("monday", "thursday", "friday"):
        if day not in days:
            continue
        details = days[day]
        resources = details.get("resources", {})
        # Older linked copies may have no selected_times of their own.
        selected = details.get("selected_times")
        source = details.get("copy_from")
        visited = {day}
        while selected is None and source in days and source not in visited:
            visited.add(source)
            selected = days[source].get("selected_times")
            source = days[source].get("copy_from")
        yield {
            "submission_id": str(submission["id"]),
            "created_at": submission["created_at"].isoformat(),
            "username": username,
            "alliance": alliance,
            "username_alliance": identity,
            "in_game_id": payload.get("in_game_id", submission["in_game_id"]),
            "appointment_day": day,
            "appointment_date": details.get("date", ""),
            "minister": details.get("minister", ""),
            "selected_times": ";".join(selected or []),
            "available_slots_utc": ";".join(details.get("available_slots_utc") or []),
            "speedups_days": resources.get("speedups_days", ""),
            "tg": resources.get("tg", ""),
            "ttg": resources.get("ttg", ""),
            "dust": resources.get("dust", ""),
            "comments": payload.get("comments", ""),
        }


def main():
    with (PROJECT_DIR / ".streamlit" / "secrets.toml").open("rb") as secrets_file:
        config = tomllib.load(secrets_file)
    url = make_url(config["DATABASE_URL"]).set(drivername="postgresql+psycopg2")
    engine = create_engine(url, connect_args={"connect_timeout": 15})
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            # app.py and the existing Neon database use this table name.
            submissions = connection.execute(text(
                "SELECT id, created_at, username_alliance, in_game_id, payload "
                "FROM ks_minister_requests ORDER BY created_at, id"
            )).mappings().all()
        output = PROJECT_DIR / "output" / "minister_requests.csv"
        row_count = 0
        with output.open("w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=COLUMNS)
            writer.writeheader()
            for submission in submissions:
                for row in flatten_submission(submission):
                    writer.writerow(row)
                    row_count += 1
        print("Columns: " + ", ".join(COLUMNS))
        print(f"Exported rows: {row_count} from {len(submissions)} submissions")
        print(f"Saved: {output.name}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Database exception messages may contain credentials or connection URLs.
        print(f"Export failed ({type(exc).__name__}). Check configuration and connectivity.", file=sys.stderr)
        sys.exit(1)
