# Config constants — total CS spots (500), seat-math assumptions, etc.
TOTAL_CS_SPOTS = 500
CSC148_AVG = 72
CSC165_AVG = 69

# Estimated CSC165 std dev (as % of test total), for modeling the course
# average as a normal distribution.
#
# How this was calculated: from the CSC165 term test stats page (2026 WINTER), each test's
# std dev was normalized to a % of that test's total (std / total), since the
# four tests have different point totals (34, 30, 34, 36) and raw std devs
# aren't comparable across them. The per-test % std devs were then weighted
# by CSC165's actual grading scheme, where the best term test counts for 20%
# of the final grade, the next-best 15%, then 10%, then 5% — the best test
# here is the one with the highest mean %:
#
#   Test   Total   Std     Mean %    Std %      Rank        Weight
#   TT2    30      5.29    79.6%     17.63%     best        20
#   TT1    34      5.92    76.2%     17.41%     2nd best    15
#   TT3    34      7.89    65.4%     23.21%     3rd best    10
#   TT4    36      8.56    54.1%     23.78%     worst       5
#
#   weighted_avg = sum(weight_i * std_pct_i) / sum(weight_i)
#                = (20*17.63 + 15*17.41 + 10*23.21 + 5*23.78) / (20+15+10+5)
#                = 964.79 / 50
#                = 19.30%
CSC165_ESTIMATED_SD_PCT = 19.30

# --- Enrollment data source (github.com/ICPRplshelp/Enrollment-Data) ---
# Per that repo's README: fetch over HTTP, do not `git clone`/fetch it, since
# the author may change how it's hosted later.
ENROLLMENT_DATA_BASE_URL = "https://raw.githubusercontent.com/ICPRplshelp/Enrollment-Data/master"

# Fall-Winter session codes to pull historical enrollment for.
# Session code format: f"{start_year}9" (see that repo's README for the "5"/"9" convention).
# 20269 (Fall-Winter 2026-2027) is excluded here since it hasn't started yet.
ENROLLMENT_SESSIONS = {
    2022: "20229",
    2023: "20239",
    2024: "20249",
    2025: "20259",
}

# CSV column name -> course file name within a session folder.
# CSC165 is Winter-only; CSC148 is tracked both terms since the Fall intake
# feeds into the Winter CSC165 applicant pool.
ENROLLMENT_COURSES = {
    "csc111_winter": "CSC111H1S.json",
    "csc148_fall": "CSC148H1F.json",
    "csc148_winter": "CSC148H1S.json",
    "csc165_winter": "CSC165H1S.json",
}

ENROLLMENT_DATA_CSV_PATH = "backend/data/enrollment_data.csv"

HISTORICAL_AVERAGES_CSV_PATH = "backend/data/historical_averages.csv"