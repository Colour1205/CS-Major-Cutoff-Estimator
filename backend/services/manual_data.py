# Admin manual edit of historical_averages.csv / safe_grades.csv — lets the
# admin correct or backfill a year's value directly, same file format the
# scraper writes.
import csv
from pathlib import Path

from backend.config import HISTORICAL_AVERAGES_CSV_PATH, MANUAL_OVERRIDES_CSV_PATH, SAFE_GRADE_CSV_PATH
from backend.services.estimate_service import OVERRIDE_FIELDS, _load_csv_by_year, _load_overrides


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


def _write_overrides(overrides: dict[int, set], path: str = MANUAL_OVERRIDES_CSV_PATH) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "field"])
        writer.writeheader()
        for year in sorted(overrides):
            for field in sorted(overrides[year]):
                writer.writerow({"year": year, "field": field})


def set_override(year: int, field: str, path: str = MANUAL_OVERRIDES_CSV_PATH) -> None:
    """Force `field` (actual_cutoff or safe_grade) to keep using the
    manual-edit CSV value for `year`, even once that year has enough
    records to normally be computed from the database instead (see
    estimate_service._effective_values). Cleared via clear_override.
    """
    if field not in OVERRIDE_FIELDS:
        raise ValueError(f"field must be one of {OVERRIDE_FIELDS}")
    overrides = _load_overrides(path)
    overrides.setdefault(year, set()).add(field)
    _write_overrides(overrides, path)


def clear_override(year: int, path: str = MANUAL_OVERRIDES_CSV_PATH) -> None:
    """Revert a year back to normal (record-based once past the
    threshold, manual-edit value below it) by dropping all of its
    force-override flags.
    """
    overrides = _load_overrides(path)
    overrides.pop(year, None)
    _write_overrides(overrides, path)
