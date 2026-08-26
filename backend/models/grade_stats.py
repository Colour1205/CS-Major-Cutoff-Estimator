# Shared statistics over a raw list of reported admit grades — used both by
# the (private, gitignored) Reddit scraper and by estimate_service when
# blending in admin-approved user submissions, so both sources are reduced
# to a year's cutoff/safe-grade the exact same way.
import math
import statistics
from collections import Counter
from typing import Optional


def report_grade(csc148: Optional[float], csc165: Optional[float], average: Optional[float]) -> Optional[float]:
    """Reduce one report's fields to a single combined grade."""
    if average is not None:
        return float(average)
    if csc148 is not None and csc165 is not None:
        return (float(csc148) + float(csc165)) / 2
    return None


def estimate_cutoff(grades: list[float], outlier_iqr_multiplier: float = 1.5) -> Optional[float]:
    """The real cutoff from a list of reported admit grades.

    Drops low outliers (noise — typos, off-topic mentions, other-campus
    posts — not real direct-entry admits) via IQR, then returns the minimum
    of what's left. Falls back to the raw minimum when there isn't enough
    data to compute quartiles, or when filtering would drop every grade.
    """
    if not grades:
        return None
    if len(grades) < 4:
        return min(grades)

    q1, _, q3 = statistics.quantiles(grades, n=4)
    iqr = q3 - q1
    lower_bound = q1 - outlier_iqr_multiplier * iqr

    reasonable = [g for g in grades if g >= lower_bound]
    return min(reasonable) if reasonable else min(grades)


def _bin(x: float, bin_width: float) -> float:
    """Round x to the nearest multiple of bin_width (round-half-up)."""
    return math.floor(x / bin_width + 0.5) * bin_width


def safe_grade(grades: list[float], bin_width: float = 3.0) -> Optional[float]:
    """The "safe" grade: not the bare cutoff (which can be misleadingly low
    — someone right at the cutoff may have only gotten in because of a
    strong supplementary application), but the grade cluster reported most
    often among people who *did* get in — e.g. "low 90s" showing up over
    and over.

    Grades are binned (default width 3) to find the most common cluster
    rather than requiring exact-value matches, then the actual reported
    values inside that winning bin are averaged for precision. Ties are
    broken toward the lower bin — the more conservative (still-safe) choice.
    """
    if not grades:
        return None
    binned = [_bin(g, bin_width) for g in grades]
    counts = Counter(binned)
    max_count = max(counts.values())
    mode_bin = min(b for b, c in counts.items() if c == max_count)  # lower bin on ties
    values_in_bin = [g for g, b in zip(grades, binned) if b == mode_bin]
    return sum(values_in_bin) / len(values_in_bin)
