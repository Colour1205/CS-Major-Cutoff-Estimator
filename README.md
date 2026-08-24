# CS Major Cutoff Estimator

Estimates the predicted UofT CS major cutoff average (based on CSC148 and CSC165) using historical data and current enrollment counts.

## Year convention

A `year` labels an academic year by its **Fall start year**. `year = 2025` means Fall 2025 – Winter 2026: CSC148 in Fall 2025, CSC165 in Winter 2026, decision released summer 2026 — the year *after* the label.

## Where the data comes from

- **Enrollment counts** (`backend/data/enrollment_data.csv`) — fetched by `backend/services/enrollment.py` from the [UofT Enrollment Tracker data](https://github.com/ICPRplshelp/Enrollment-Data) (see Credits).
- **Historical cutoffs** (`backend/data/historical_averages.csv`) — the real minimum combined csc148/csc165 average that got someone in, per year. Mostly scraped from Reddit (`backend/scraper/reddit_scraper.py`): since Reddit blocks automated API access, posts/comments are collected via a browser extension (`tools/webscraper_sitemap.json` for Web Scraper, or `tools/reddit_snippet_collector.user.js` for Tampermonkey) instead, then sent to OpenAI to extract structured `{decision_year, csc148, csc165, average, program}` reports. The `program` field filters out Data Science specialist / CS minor reports, which have different cutoffs than the CS major. The year is then converted to our Fall-start convention in plain code (`year = decision_year - 1`), and the cutoff for a year is the lowest report remaining after dropping outliers via IQR. Years with too few reports to trust are filled in manually instead.

## How the estimate is computed

`backend/models/estimator.py`:

1. **Seat math**: `out_of_stream_spots = 500 - csc111_winter` (everyone in CSC111 instream is assumed admitted); `csc165_winter` is the out-of-stream applicant pool (CSC165 is Winter-only with lower enrollment than CSC148, so everyone in it is assumed to have already passed CSC148).
2. **Distribution model**: the combined average is modeled as a **Beta distribution**, moment-matched to mean `(CSC148_AVG + CSC165_AVG) / 2` and std dev `CSC165_ESTIMATED_SD_PCT` (derived from CSC165 term-test stats — see `backend/config.py`). Beta over a plain normal because it's bounded to [0, 100] (an unbounded normal produced impossible >100% values during backtesting) and comes out naturally left-skewed toward higher marks, matching real grade distributions. The raw estimate is this distribution's inverse-CDF at the `out_of_stream_spots / csc165_winter` percentile.
3. **Calibration**: the current year's raw estimate is adjusted by the average error (`estimate - actual`) across all years with a known actual cutoff.

### Safe grade (`GET /api/estimate/safe`)

The bare cutoff can be misleading — the person right at it may have only gotten in via a strong supplementary application, so plenty of others at that exact grade get rejected. The **safe grade** is a comfortably-likely-to-get-in alternative: the grade cluster reported most often among people who *did* get in (e.g. "low 90s" showing up repeatedly), found by binning each year's raw scraped grades (`backend/data/safe_grades.csv`) and taking the most common bin.

For each year with both a safe grade and an actual cutoff on record, `distance = safe_grade - actual_cutoff` is computed; the average of those distances is added on top of the calibrated cutoff estimate for the current year (`Estimator.estimate_safe_grade`).

## Backtesting

Validated with leave-one-out backtesting — each year predicted using only *prior* years for calibration, compared against what actually happened. This caught a real bug: an earlier unbounded-normal version predicted an impossible 102% cutoff for 2024; switching to Beta cut that year's error from +14.97 to +6.20 and overall MAE from 7.63 to 4.05.

| Year | Actual | Predicted | Error |
|---|---|---|---|
| 2023 | 78.0 | 78.28 | +0.28 |
| 2024 | 85.0 | 91.20 | +6.20 |
| 2025 | 89.0 | 83.34 | -5.66 |

MAE: 4.05, RMSE: 4.85, Bias: +0.27

## Known limitations

- Only 3-4 years of calibration data — the correction is itself noisy.
- 2024/2025 cutoffs are partly manual, not IQR-filtered from a large Reddit sample like earlier years.
- Program classification (major vs. DS specialist vs. minor) isn't independently verified.
- `TOTAL_CS_SPOTS = 500` is a constant across all years; may not reflect real year-to-year variation.
- `safe_grades.csv`'s 2021-2023 rows come from a large enough raw Reddit sample to bin into a real mode; 2024/2025 don't have that data, so those two rows are themselves *model-estimated* (that year's actual_cutoff + the average distance from 2021-2023) rather than independently observed — the safe-grade calibration is based on just 3 real data points and hasn't been backtested the way the cutoff model was.

## Credits

Enrollment data is sourced from [ICPRplshelp/Enrollment-Data](https://github.com/ICPRplshelp/Enrollment-Data), created for the [UofT Enrollment Tracker](https://github.com/ICPRplshelp/UofT-Enrollment-Tracker), sourced from https://ttb.utoronto.ca/. Per that repo's terms, data is fetched over HTTP rather than via Git, since the author may change hosting at any time.
