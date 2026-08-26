# One-time migration: the individual raw admit-grade reports recovered
# during the original Reddit-scraping pass for 2021-2023 (see the scraper's
# IQR-filtered, program-classified output that historical_averages.csv /
# safe_grades.csv were originally computed from), imported into
# scraped_grades so the database — not a single derived scalar — is the
# source of truth going forward. Safe to re-run: import_scraped_grades
# skips a year that already has scraped_grades rows.
from backend.services.submissions import import_scraped_grades

SCRAPED_GRADES_BY_YEAR = {
    2021: [
        88.0, 88.0, 89.5, 90.0, 90.0, 90.5, 90.5, 90.5, 91.5, 92.0,
        92.0, 92.5, 92.5, 92.5, 94.0, 94.5, 94.5, 98.0, 98.0, 99.25,
    ],
    2022: [
        83.5, 84.5, 85.5, 86.0, 89.0, 89.0, 89.5, 90.0, 92.5, 94.5, 96.5, 97.0,
    ],
    2023: [
        78.0, 78.0, 80.0, 80.0, 81.0, 83.0, 85.0, 85.0, 85.5, 90.0,
        90.0, 90.0, 90.0, 90.5, 90.5, 90.5, 92.0, 92.5, 93.0, 93.5,
        95.0, 96.0, 100.0,
    ],
}


def run() -> None:
    for year, grades in SCRAPED_GRADES_BY_YEAR.items():
        import_scraped_grades(year, grades)
        print(f"{year}: {len(grades)} records")


if __name__ == "__main__":
    run()
