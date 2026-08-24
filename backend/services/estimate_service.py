# Service layer: loads enrollment + historical data and runs Estimator to
# produce the cutoff and safe-grade estimates the API exposes.
import csv

from backend.config import ENROLLMENT_DATA_CSV_PATH, HISTORICAL_AVERAGES_CSV_PATH, SAFE_GRADE_CSV_PATH
from backend.models.estimator import Estimator


def _load_csv_by_year(path: str) -> dict[int, dict]:
    with open(path, newline="") as f:
        return {int(row["year"]): row for row in csv.DictReader(f)}


def load_merged_data(
    enrollment_path: str = ENROLLMENT_DATA_CSV_PATH,
    averages_path: str = HISTORICAL_AVERAGES_CSV_PATH,
) -> dict[int, dict]:
    """Load enrollment_data.csv and historical_averages.csv, merged by year.

    Keyed by every year present in enrollment_data.csv (the seat-math side is
    required to estimate a year at all). A year missing from
    historical_averages.csv just has no `actual_cutoff` key — Estimator
    treats that as "nothing to calibrate against for this year," not an
    error, so the current/latest year (which never has an actual cutoff yet)
    still works.
    """
    enrollment_by_year = _load_csv_by_year(enrollment_path)
    averages_by_year = _load_csv_by_year(averages_path)

    return {
        year: {**enrollment, **averages_by_year.get(year, {})}
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

    actual_cutoff_by_year = {
        year: row.get("actual_cutoff") for year, row in _load_csv_by_year(averages_path).items()
    }
    safe_grade_by_year = {
        year: row.get("safe_grade") for year, row in _load_csv_by_year(safe_grade_path).items()
    }

    latest_year = max(data.keys())
    estimated_safe_grade = Estimator(data).estimate_safe_grade(actual_cutoff_by_year, safe_grade_by_year)

    return {
        "year": latest_year,
        "estimated_safe_grade": round(estimated_safe_grade, 2),
    }
