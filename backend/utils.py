# Shared helpers for anywhere a "school year" range needs to be offered or
# validated (the submit-mark year selector, the admin manual-edit selector,
# and the public API's own validation of a submitted year).
from datetime import datetime

MIN_SCHOOL_YEAR = 2021


def current_school_year_start() -> int:
    """The most recent school year (Fall start) that has begun.

    Advances automatically every September 1st -- no manual bump needed as
    real time passes.
    """
    now = datetime.now()
    return now.year if now.month >= 9 else now.year - 1
