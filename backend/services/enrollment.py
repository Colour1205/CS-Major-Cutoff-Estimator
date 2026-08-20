# Seat math — instream/out-of-stream split, csc111 -> csc148 -> csc165 funnel logic.
# Also fetches historical enrollment counts from the UofT Enrollment Tracker data
# (github.com/ICPRplshelp/Enrollment-Data) and writes them to enrollment_data.csv.

import csv
import sys
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parents[2]))
from backend.config import (
    ENROLLMENT_COURSES,
    ENROLLMENT_DATA_BASE_URL,
    ENROLLMENT_DATA_CSV_PATH,
    ENROLLMENT_SESSIONS,
)


def fetch_course_json(session_code: str, filename: str) -> dict | None:
    """Fetch one course's enrollment-tracker JSON for a given session.

    Returns None if the course wasn't offered that session (404).
    """
    url = f"{ENROLLMENT_DATA_BASE_URL}/{session_code}/{filename}"
    response = requests.get(url, timeout=15)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def final_enrollment(course_json: dict) -> int:
    """Sum the last enrollmentLogs value across all meetings/sections.

    enrollmentLogs is a daily time series for the term; the last entry is
    the settled end-of-term enrollment for that section.
    """
    total = 0
    for meeting in course_json.get("meetings", []):
        logs = meeting.get("enrollmentLogs", [])
        if logs:
            total += logs[-1]
    return total


def build_enrollment_table() -> list[dict]:
    """Fetch enrollment counts for every tracked course, for every session.

    Returns one row per year, e.g.
    {"year": 2024, "csc111_winter": 120, "csc148_fall": 850, ...}
    """
    rows = []
    for year, session_code in sorted(ENROLLMENT_SESSIONS.items()):
        row = {"year": year}
        for column, filename in ENROLLMENT_COURSES.items():
            course_json = fetch_course_json(session_code, filename)
            row[column] = final_enrollment(course_json) if course_json else ""
        rows.append(row)
    return rows


def write_enrollment_csv(rows: list[dict], path: str = ENROLLMENT_DATA_CSV_PATH) -> None:
    fieldnames = ["year", *ENROLLMENT_COURSES.keys()]
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    write_enrollment_csv(build_enrollment_table())
