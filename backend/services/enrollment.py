# Seat math — instream/out-of-stream split, csc111 -> csc148 -> csc165 funnel logic.
# Also fetches historical enrollment counts from the UofT Enrollment Tracker data
# (github.com/ICPRplshelp/Enrollment-Data) and writes them to enrollment_data.csv.

import csv
import sys
import threading
import time
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
    A column is "" when that course's file doesn't exist yet for that
    session (e.g. a Winter course whose enrollment hasn't opened yet).
    """
    rows = []
    for year, session_code in sorted(ENROLLMENT_SESSIONS.items()):
        row = {"year": year}
        for column, filename in ENROLLMENT_COURSES.items():
            course_json = fetch_course_json(session_code, filename)
            row[column] = final_enrollment(course_json) if course_json else ""
        rows.append(row)
    return rows


def _linear_forecast(known_years: list[int], known_values: list[float], target_year: int) -> float:
    """Least-squares linear trend, extrapolated to target_year."""
    n = len(known_years)
    if n == 1:
        return known_values[0]

    mean_x = sum(known_years) / n
    mean_y = sum(known_values) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(known_years, known_values))
    denominator = sum((x - mean_x) ** 2 for x in known_years)
    slope = numerator / denominator if denominator else 0.0
    intercept = mean_y - slope * mean_x

    return slope * target_year + intercept


def forecast_missing_columns(rows: list[dict]) -> list[dict]:
    """Fill any missing ("") column values with a linear-trend forecast from
    that column's other years, rounded to the nearest non-negative int.

    This covers a year whose enrollment tracker files don't exist yet (most
    notably csc165_winter for a session whose Winter term hasn't run yet —
    UofT opens enrollment for the whole Fall-Winter session around July, so
    this gap is usually brief, but the estimator shouldn't have to sit idle
    until every column is real). Real fetched data always takes priority —
    this only ever fills a genuine blank, never overwrites a real value.
    """
    if not rows:
        return rows

    columns = [c for c in rows[0] if c != "year"]
    for row in rows:
        for column in columns:
            if row[column] != "":
                continue
            known = [(r["year"], r[column]) for r in rows if r is not row and r[column] != ""]
            if not known:
                continue
            known_years = [y for y, _ in known]
            known_values = [float(v) for _, v in known]
            forecast = _linear_forecast(known_years, known_values, row["year"])
            row[column] = round(max(forecast, 0))
    return rows


def write_enrollment_csv(rows: list[dict], path: str = ENROLLMENT_DATA_CSV_PATH) -> None:
    fieldnames = ["year", *ENROLLMENT_COURSES.keys()]
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def refresh_enrollment_csv(path: str = ENROLLMENT_DATA_CSV_PATH) -> None:
    """Fetch the latest enrollment data, forecast any still-missing columns,
    and write it out — the single call both the CLI entry point and the
    background refresh loop use.
    """
    write_enrollment_csv(forecast_missing_columns(build_enrollment_table()), path)


def start_background_refresh(interval_seconds: int = 86400) -> None:
    """Start a daemon thread that re-runs refresh_enrollment_csv once a day.

    Once the Enrollment Tracker repo publishes real data for a column that
    was previously forecasted, this picks it up automatically and
    overwrites the forecast with the real number — no manual re-run needed.
    """
    def loop():
        while True:
            try:
                refresh_enrollment_csv()
            except Exception as e:
                print(f"[enrollment refresh] failed: {e}")
            time.sleep(interval_seconds)

    threading.Thread(target=loop, daemon=True).start()


if __name__ == "__main__":
    refresh_enrollment_csv()
