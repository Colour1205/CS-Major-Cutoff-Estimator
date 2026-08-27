# Grade records, in one SQLite database with two sections (tables):
#   - submissions: user-submitted reports, gated behind admin approval
#     before they count toward any estimate.
#   - scraped_grades: individual historical reports recovered from the
#     Reddit-scraping pipeline (see backend/scraper/, gitignored/private) —
#     always trusted/counted, since that pipeline already did its own
#     IQR-based vetting before these were saved.
# SQLite since this is genuinely relational and changes over time
# (pending -> approved/rejected) — a CSV/JSON file doesn't fit as well as
# it does for a single scalar per year.
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.config import GRADES_DB_PATH
from backend.models.grade_stats import report_grade

VALID_STATUSES = ("pending", "approved", "rejected")


@contextmanager
def _connect(path: str = GRADES_DB_PATH):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: str = GRADES_DB_PATH) -> None:
    with _connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                csc148 REAL,
                csc165 REAL,
                average REAL,
                status TEXT NOT NULL DEFAULT 'pending',
                submitted_at TEXT NOT NULL,
                ip_hash TEXT
            )
        """)
        # ip_hash was added after this table already existed for some
        # installs -- ALTER TABLE ADD COLUMN if an older DB is missing it.
        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(submissions)")}
        if "ip_hash" not in existing_columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN ip_hash TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scraped_grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                csc148 REAL,
                csc165 REAL,
                average REAL,
                imported_at TEXT NOT NULL
            )
        """)


def create_submission(
    year: int,
    csc148: Optional[float],
    csc165: Optional[float],
    average: Optional[float],
    ip_hash: Optional[str] = None,
    path: str = GRADES_DB_PATH,
) -> int:
    """Insert a new submission as pending. Never touches the live estimate —
    only an admin-approved submission does (see estimate_service).

    ip_hash is a salted hash of the submitter's IP (see
    backend.api.routes.hash_ip) -- never the raw IP itself -- so the admin
    dashboard can flag "these N pending submissions came from the same
    source" without this app ever persisting anyone's actual address.
    """
    if report_grade(csc148, csc165, average) is None:
        raise ValueError("submission needs either `average`, or both `csc148` and `csc165`")

    init_db(path)
    with _connect(path) as conn:
        cursor = conn.execute(
            "INSERT INTO submissions (year, csc148, csc165, average, status, submitted_at, ip_hash) "
            "VALUES (?, ?, ?, ?, 'pending', ?, ?)",
            (year, csc148, csc165, average, datetime.now(timezone.utc).isoformat(), ip_hash),
        )
        return cursor.lastrowid


def create_approved_submission(
    year: int,
    csc148: Optional[float],
    csc165: Optional[float],
    average: Optional[float],
    path: str = GRADES_DB_PATH,
) -> int:
    """Insert a submission that's already approved — for admin-entered data
    (e.g. the AI-paste-extraction tool), which doesn't need a review queue
    since the admin is the one who just reviewed it.
    """
    submission_id = create_submission(year, csc148, csc165, average, ip_hash=None, path=path)
    update_submission_status(submission_id, "approved", path)
    return submission_id


def list_submissions(status: Optional[str] = None, path: str = GRADES_DB_PATH) -> list[dict]:
    init_db(path)
    with _connect(path) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM submissions WHERE status = ? ORDER BY submitted_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM submissions ORDER BY submitted_at DESC").fetchall()
        return [dict(row) for row in rows]


def update_submission_status(submission_id: int, status: str, path: str = GRADES_DB_PATH) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}")

    init_db(path)
    with _connect(path) as conn:
        conn.execute("UPDATE submissions SET status = ? WHERE id = ?", (status, submission_id))


def import_scraped_grades(year: int, grades: list[float], path: str = GRADES_DB_PATH) -> None:
    """Bulk-insert individual historical reports recovered from the (private)
    Reddit-scraping pipeline. Skips years that already have scraped_grades
    rows, so re-running a migration script is safe/idempotent.
    """
    init_db(path)
    with _connect(path) as conn:
        existing = conn.execute("SELECT 1 FROM scraped_grades WHERE year = ? LIMIT 1", (year,)).fetchone()
        if existing:
            return
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "INSERT INTO scraped_grades (year, csc148, csc165, average, imported_at) VALUES (?, NULL, NULL, ?, ?)",
            [(year, grade, now) for grade in grades],
        )


def list_scraped_grades(year: Optional[int] = None, path: str = GRADES_DB_PATH) -> list[dict]:
    init_db(path)
    with _connect(path) as conn:
        if year is not None:
            rows = conn.execute("SELECT * FROM scraped_grades WHERE year = ? ORDER BY id", (year,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM scraped_grades ORDER BY year, id").fetchall()
        return [dict(row) for row in rows]


def get_approved_grades_by_year(path: str = GRADES_DB_PATH) -> dict[int, list[float]]:
    """Every approved submission's grade AND every scraped_grades row,
    grouped by year — this is the full, granular record set a year's
    cutoff/safe-grade gets computed from (see estimate_service).
    """
    grades_by_year: dict[int, list[float]] = {}

    for row in list_submissions(status="approved", path=path):
        grade = report_grade(row["csc148"], row["csc165"], row["average"])
        if grade is not None:
            grades_by_year.setdefault(row["year"], []).append(grade)

    for row in list_scraped_grades(path=path):
        grade = report_grade(row["csc148"], row["csc165"], row["average"])
        if grade is not None:
            grades_by_year.setdefault(row["year"], []).append(grade)

    return grades_by_year
