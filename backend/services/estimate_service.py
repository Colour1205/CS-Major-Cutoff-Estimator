# Service layer: loads enrollment + historical data and runs Estimator to
# produce the cutoff and safe-grade estimates the API exposes.
import csv

from backend.config import ENROLLMENT_DATA_CSV_PATH, HISTORICAL_AVERAGES_CSV_PATH, SAFE_GRADE_CSV_PATH
from backend.models import grade_stats
from backend.models.estimator import Estimator
from backend.services.submissions import get_approved_grades_by_year


def _load_csv_by_year(path: str) -> dict[int, dict]:
    with open(path, newline="") as f:
        return {int(row["year"]): row for row in csv.DictReader(f)}


def _effective_values(year: int, averages_by_year: dict, safe_by_year: dict, approved_by_year: dict) -> dict:
    """A year's effective cutoff/safe grade.

    When the database has any individual records for a year (scraped
    historical reports + admin-approved submissions — see
    submissions.get_approved_grades_by_year), those records are
    authoritative: cutoff/safe grade are computed directly from that full
    list via the same IQR-cutoff / mode-binning logic the Reddit scraper
    uses (grade_stats). The historical_averages.csv/safe_grades.csv scalar
    is only a *fallback* for a year with no granular records at all yet
    (e.g. 2024/2025 today) — once real records exist for a year, the CSV
    scalar for that year is no longer consulted, avoiding double-counting
    a value that's now redundant with its own constituent data.
    """
    records = approved_by_year.get(year, [])
    if records:
        return {
            "actual_cutoff": grade_stats.estimate_cutoff(records),
            "safe_grade": grade_stats.safe_grade(records),
        }

    existing_cutoff = averages_by_year.get(year, {}).get("actual_cutoff")
    existing_safe_grade = safe_by_year.get(year, {}).get("safe_grade")
    return {
        "actual_cutoff": float(existing_cutoff) if existing_cutoff not in (None, "") else None,
        "safe_grade": float(existing_safe_grade) if existing_safe_grade not in (None, "") else None,
    }


def load_merged_data(
    enrollment_path: str = ENROLLMENT_DATA_CSV_PATH,
    averages_path: str = HISTORICAL_AVERAGES_CSV_PATH,
) -> dict[int, dict]:
    """Load enrollment_data.csv and historical_averages.csv, merged by year.

    Keyed by every year present in enrollment_data.csv (the seat-math side is
    required to estimate a year at all). `actual_cutoff` reflects any
    admin-approved user submissions for that year too (see _effective_values).
    A year with no actual_cutoff at all just has that key as None — Estimator
    treats that as "nothing to calibrate against for this year," not an
    error, so the current/latest year (which never has an actual cutoff yet)
    still works.
    """
    enrollment_by_year = _load_csv_by_year(enrollment_path)
    averages_by_year = _load_csv_by_year(averages_path)
    approved_by_year = get_approved_grades_by_year()

    return {
        year: {
            **enrollment,
            "actual_cutoff": _effective_values(year, averages_by_year, {}, approved_by_year)["actual_cutoff"],
        }
        for year, enrollment in enrollment_by_year.items()
    }


def get_latest_estimate() -> dict:
    """Return the estimated cutoff average for the most recent year on record."""
    data = load_merged_data()
    if not data:
        raise ValueError("no data available to estimate from")

    latest_year = max(data.keys())
    estimated_cutoff = Estimator(data).estimate_cutoff()

    return {
        "year": latest_year,
        "estimated_cutoff": round(estimated_cutoff, 2),
    }


def get_latest_safe_grade_estimate(
    averages_path: str = HISTORICAL_AVERAGES_CSV_PATH,
    safe_grade_path: str = SAFE_GRADE_CSV_PATH,
) -> dict:
    """Return the estimated "safe" grade for the most recent year — a grade
    comfortably likely to get in, not just the bare (possibly
    supplementary-application-skewed) cutoff. See Estimator.estimate_safe_grade.
    """
    data = load_merged_data()
    if not data:
        raise ValueError("no data available to estimate from")

    averages_by_year = _load_csv_by_year(averages_path)
    safe_by_year = _load_csv_by_year(safe_grade_path)
    approved_by_year = get_approved_grades_by_year()

    all_years = set(averages_by_year) | set(safe_by_year) | set(approved_by_year)
    actual_cutoff_by_year = {}
    safe_grade_by_year = {}
    for year in all_years:
        effective = _effective_values(year, averages_by_year, safe_by_year, approved_by_year)
        if effective["actual_cutoff"] is not None:
            actual_cutoff_by_year[year] = effective["actual_cutoff"]
        if effective["safe_grade"] is not None:
            safe_grade_by_year[year] = effective["safe_grade"]

    latest_year = max(data.keys())
    estimated_safe_grade = Estimator(data).estimate_safe_grade(actual_cutoff_by_year, safe_grade_by_year)

    return {
        "year": latest_year,
        "estimated_safe_grade": round(estimated_safe_grade, 2),
    }


def get_history(
    averages_path: str = HISTORICAL_AVERAGES_CSV_PATH,
    safe_grade_path: str = SAFE_GRADE_CSV_PATH,
) -> list[dict]:
    """Per-year actual_cutoff + safe_grade (including admin-approved
    submissions), for charting historical trends.

    Not gated on enrollment data being present (unlike load_merged_data) —
    this is just the historical record, which the seat-math model doesn't
    need to exist.
    """
    averages_by_year = _load_csv_by_year(averages_path)
    safe_by_year = _load_csv_by_year(safe_grade_path)
    approved_by_year = get_approved_grades_by_year()
    years = sorted(set(averages_by_year) | set(safe_by_year) | set(approved_by_year))

    result = []
    for year in years:
        effective = _effective_values(year, averages_by_year, safe_by_year, approved_by_year)
        result.append({
            "year": year,
            "actual_cutoff": round(effective["actual_cutoff"], 2) if effective["actual_cutoff"] is not None else None,
            "safe_grade": round(effective["safe_grade"], 2) if effective["safe_grade"] is not None else None,
        })
    return result
