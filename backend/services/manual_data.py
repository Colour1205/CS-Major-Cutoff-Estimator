# Admin manual edit of historical_averages.csv / safe_grades.csv — lets the
# admin correct or backfill a year's value directly, same file format the
# scraper writes.
import csv
from pathlib import Path

from backend.config import HISTORICAL_AVERAGES_CSV_PATH, SAFE_GRADE_CSV_PATH
from backend.services.estimate_service import _load_csv_by_year


def _write_year_value_csv(path: str, value_column: str, year: int, value: float) -> None:
    rows = _load_csv_by_year(path) if Path(path).exists() else {}
    rows[year] = {"year": year, value_column: value}

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", value_column])
        writer.writeheader()
        for y in sorted(rows):
            writer.writerow({"year": y, value_column: rows[y][value_column]})


def set_actual_cutoff(year: int, value: float, path: str = HISTORICAL_AVERAGES_CSV_PATH) -> None:
    _write_year_value_csv(path, "actual_cutoff", year, value)


def set_safe_grade(year: int, value: float, path: str = SAFE_GRADE_CSV_PATH) -> None:
    _write_year_value_csv(path, "safe_grade", year, value)
