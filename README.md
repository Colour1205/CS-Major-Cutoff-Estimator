# CS Major Cutoff Estimator

Estimates the predicted UofT CS major cutoff average (based on CSC148 and CSC165) using historical data and current enrollment counts.

## Year convention

A `year` labels an academic year by its **Fall start year**. `year = 2025` means Fall 2025 – Winter 2026 academic year.

## How the estimate is computed

`backend/models/estimator.py`:

1. **Seat math (deliberately worst-case)**: `out_of_stream_spots = 500 - csc111_winter` assumes *everyone* in CSC111 instream is admitted, and `csc165_winter` (the out-of-stream applicant pool) assumes *everyone* in it applies for CS. Both assumptions maximize assumed competition for the remaining spots, so the raw estimate leans toward the higher end of what could actually happen.
2. **Distribution model**: the combined average is modeled as a **Beta distribution**, moment-matched to mean `(CSC148_AVG + CSC165_AVG) / 2` and std dev `CSC165_ESTIMATED_SD_PCT` (derived from CSC165 term-test stats in my class (2026), see `backend/config.py`). I chose beta distribution since it better matches the skewed shape of grades distribution and is bounded.

### Safe grade (`GET /api/estimate/safe`)

The bare cutoff can be misleading, the person right at it may have only gotten in via a strong supplementary application, so plenty of others at that exact grade get rejected. The **safe grade** is a comfortably-likely-to-get-in alternative: the grade cluster reported most often among people who *did* get in (e.g. "low 90s" showing up repeatedly), found by binning each year's raw scraped grades (`backend/data/safe_grades.csv`) and taking the most common bin.

For each year with both a safe grade and an actual cutoff on record, `distance = safe_grade - actual_cutoff` is computed; the average of those distances is added on top of the calibrated cutoff estimate for the current year (`Estimator.estimate_safe_grade`).

## Backtesting

Each year predicted using only *prior* years for calibration, compared against what actually happened.

| Year | Actual | Predicted | Error |
|---|---|---|---|
| 2023 | 78.0 | 78.28 | +0.28 |
| 2024 | 85.0 | 91.20 | +6.20 |
| 2025 | 83.0 | 83.34 | +0.34 |

Bias: +2.27. Every single prediction so far has come in at or above the actual cutoff, never below. That's the expected shape of a worst-case model (see Seat math above), since the underlying seat-math assumptions already lean toward maximum competition.

This runs as `backend/services/backtest.py`, cached to `backend/data/backtest_results.json` and served via `GET /api/backtest` — `backend/app.py` recomputes it hourly in the background.

## Where the data comes from

- **Enrollment counts** (`backend/data/enrollment_data.csv`) — fetched by `backend/services/enrollment.py` from the [UofT Enrollment Tracker data](https://github.com/ICPRplshelp/Enrollment-Data) (see Credits). Any column still missing for the most recent year (e.g. `csc165_winter` before that Winter term's enrollment has settled) is filled in with a linear-trend forecast from prior years (`forecast_missing_columns`) rather than left blank. `backend/app.py` runs `start_background_refresh()` on startup, which re-fetches once a day in a background thread so forecasts get replaced with real numbers automatically as they appear.
- **Historical cutoffs** (`backend/data/historical_averages.csv` + `backend/data/grades.db`) — the real minimum combined csc148/csc165 average that got someone in, per year. Mostly scraped from Reddit
  - The individual raw reports behind this (not just a single final number) live in `grades.db`'s `scraped_grades` table (seeded via `backend/services/migrate_scraped_grades.py`, which runs automatically on startup). A year's cutoff/safe grade is computed directly from these records once there are at least `MIN_RECORDS_TO_OVERRIDE` (10) of them combined; below that, `historical_averages.csv`/`safe_grades.csv`'s scalar is used instead — a handful of new records shouldn't be able to swing an established year off a tiny, unrepresentative sample.
  - **Public submissions**: anyone can submit a grade via the frontend's "Submit your mark" button (`POST /api/submissions`), stored in `grades.db`'s `submissions` table as `pending`. Pending submissions never affect the estimate — only after an admin approves one (see Admin site below) does it join the record set. Each submission is tagged with a salted hash of the submitter's IP (`backend.api.routes.hash_ip`) — never the IP itself — so the admin dashboard can flag multiple submissions from the same source without this app ever storing anyone's actual address.

## API summary

| Endpoint | Returns |
|---|---|
| `GET /api/estimate` | `{year, estimated_cutoff}` for the target year |
| `GET /api/estimate/safe` | `{year, estimated_safe_grade}` for the target year |
| `GET /api/history` | `[{year, actual_cutoff, safe_grade}, ...]` — for the frontend chart |
| `GET /api/backtest` | Cached leave-one-out backtest results + summary stats |
| `POST /api/submissions` | Submit a grade report (`{year, csc148, csc165, average}`) for admin review |

## School year display

Everywhere a year is shown to a user (chart, tables, the submit-mark and manual-edit selectors), it's spelled out as `YYYY-YY` (e.g. `2024-25`) rather than a bare year, since our internal `year` (Fall-start) convention would otherwise read as a single calendar year. The selectable range runs from `2021` (`backend/utils.MIN_SCHOOL_YEAR`) through whichever school year has most recently started — that upper bound advances automatically every September 1st (`backend/utils.current_school_year_start`), no manual bump needed.

## Known limitations

- Only 3-4 years of calibration data — the correction is itself noisy.
- 2024/2025 cutoffs are partly manual, not IQR-filtered from a large Reddit sample like earlier years. (Feel free to submit the grades on the website if you have)
- Program classification (major vs. DS specialist vs. minor) isn't independently verified.
- `TOTAL_CS_SPOTS = 500` is a constant across all years; may not reflect real year-to-year variation.
- The estimated year's enrollment counts can shift day to day, the estimator will automatically refresh everyday, but expect lower enrollment toward end of course since people drop it.
- 2021-2023 have real records in `grades.db` (`scraped_grades`) to compute a safe grade from directly; 2024/2025 don't yet, so their `safe_grades.csv` fallback values are themselves *model-estimated* (that year's actual_cutoff + the average distance from 2021-2023). the safe-grade calibration is based on just 3 real data points and hasn't been backtested the way the cutoff model was. This resolves itself automatically as more years accumulate real records (via scraping, manual input, or approved public submissions).
- `grades.db` is local runtime state (gitignored) — a fresh clone only has the `scraped_grades` seed (auto-migrated on startup); any admin-approved submissions or manual edits made on one deployment don't carry over to another.

## Admin site (`/admin`)

A separate area (not linked from the public page), gated behind a password login (`ADMIN_PASSWORD` env var, session-based auth — see `backend/api/admin_routes.py`):

- **Approve/reject pending submissions.**
- **Manually edit a year's cutoff/safe grade** directly (only takes effect below the `MIN_RECORDS_TO_OVERRIDE` threshold — see above).
- **AI paste-and-extract**: paste raw text (a Reddit thread, etc.) and OpenAI (`backend/services/ai_extraction.py`, needs `OPENAI_API_KEY`) extracts individual grade reports for review before adding.

Every decision (approve/reject, manual edit, AI-extract confirm) immediately recomputes `backtest_results.json` rather than waiting for the hourly background refresh.

## Environment variables

| Variable | Needed for |
|---|---|
| `ADMIN_PASSWORD` | `/admin` login. Unset means admin login always fails. |
| `SECRET_KEY` | Stable admin sessions across restarts (falls back to a random key otherwise). |
| `OPENAI_API_KEY` | The scraper's extraction and the admin AI-paste-extract tool. |

## Credits

Enrollment data is sourced from [ICPRplshelp/Enrollment-Data](https://github.com/ICPRplshelp/Enrollment-Data), created for the [UofT Enrollment Tracker](https://github.com/ICPRplshelp/UofT-Enrollment-Tracker), sourced from https://ttb.utoronto.ca/. Per that repo's terms, data is fetched over HTTP rather than via Git, since the author may change hosting at any time.
