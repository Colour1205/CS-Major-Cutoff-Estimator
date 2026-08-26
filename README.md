# CS Major Cutoff Estimator

Estimates the predicted UofT CS major cutoff average (based on CSC148 and CSC165) using historical data and current enrollment counts.

## Year convention

A `year` labels an academic year by its **Fall start year**. `year = 2025` means Fall 2025 – Winter 2026: CSC148 in Fall 2025, CSC165 in Winter 2026, decision released summer 2026 — the year *after* the label.

## Where the data comes from

- **Enrollment counts** (`backend/data/enrollment_data.csv`) — fetched by `backend/services/enrollment.py` from the [UofT Enrollment Tracker data](https://github.com/ICPRplshelp/Enrollment-Data) (see Credits). Any column still missing for the most recent year (e.g. `csc165_winter` before that Winter term's enrollment has settled) is filled in with a linear-trend forecast from prior years (`forecast_missing_columns`) rather than left blank — real data always overwrites a forecast once it exists. `backend/app.py` runs `start_background_refresh()` on startup, which re-fetches once a day in a background thread so forecasts get replaced with real numbers automatically as they appear.
- **Historical cutoffs** (`backend/data/historical_averages.csv` + `backend/data/grades.db`) — the real minimum combined csc148/csc165 average that got someone in, per year. Mostly scraped from Reddit (`backend/scraper/reddit_scraper.py`, gitignored/private): since Reddit blocks automated API access, posts/comments are collected via a browser extension (`tools/webscraper_sitemap.json` for Web Scraper, or `tools/reddit_snippet_collector.user.js` for Tampermonkey) instead, then sent to OpenAI to extract structured `{decision_year, csc148, csc165, average, program}` reports. The `program` field filters out Data Science specialist / CS minor reports, which have different cutoffs than the CS major. The year is then converted to our Fall-start convention in plain code (`year = decision_year - 1`).
  - The individual raw reports behind this (not just a single final number) live in `grades.db`'s `scraped_grades` table (seeded via `backend/services/migrate_scraped_grades.py`, which runs automatically on startup). A year's cutoff/safe grade is computed directly from these records when they exist; `historical_averages.csv`/`safe_grades.csv` are only a fallback for a year with no granular records yet.
  - **Public submissions**: anyone can submit a grade via the frontend's "Submit your mark" button (`POST /api/submissions`), stored in `grades.db`'s `submissions` table as `pending`. Pending submissions never affect the estimate — only after an admin approves one (see below) does it join the record set the same way a scraped grade does.

## Admin site (`/admin`)

A separate area (not linked from the public page), gated behind a password login (`ADMIN_PASSWORD` env var, session-based auth — see `backend/api/admin_routes.py`):

- **Approve/reject pending submissions.**
- **Manually edit a year's cutoff/safe grade** directly (only takes effect for a year with no granular records yet — see above).
- **AI paste-and-extract**: paste raw text (a Reddit thread, etc.) and OpenAI (`backend/services/ai_extraction.py`, needs `OPENAI_API_KEY_OTHER`) extracts individual grade reports for review before adding — same extraction approach as the scraper, but for one-off manual imports.
- **Server info**: enrollment years on record, submission counts, scraped-record counts.

Every mutation (approve/reject, manual edit, AI-extract confirm) immediately recomputes `backtest_results.json` rather than waiting for the hourly background refresh.

## How the estimate is computed

`backend/models/estimator.py`:

1. **Seat math (deliberately worst-case)**: `out_of_stream_spots = 500 - csc111_winter` assumes *everyone* in CSC111 instream is admitted, and `csc165_winter` (the out-of-stream applicant pool) assumes *everyone* in it applies for CS. Both assumptions maximize assumed competition for the remaining spots, so the raw estimate leans toward the harder end of what could actually happen rather than the average case — it's meant to be a safe number to plan around, not a most-likely guess. This is why the estimate is expected to sit *above* the real cutoff more often than not (see the positive bias in Backtesting below), not a sign the model is broken.
2. **Distribution model**: the combined average is modeled as a **Beta distribution**, moment-matched to mean `(CSC148_AVG + CSC165_AVG) / 2` and std dev `CSC165_ESTIMATED_SD_PCT` (derived from CSC165 term-test stats — see `backend/config.py`). Beta over a plain normal because it's bounded to [0, 100] (an unbounded normal produced impossible >100% values during backtesting) and comes out naturally left-skewed toward higher marks, matching real grade distributions. The raw estimate is this distribution's inverse-CDF at the `out_of_stream_spots / csc165_winter` percentile.
3. **Calibration**: the raw estimate for the target year (the most recent year in the data — normally the upcoming, not-yet-resolved cycle) is adjusted by the average error (`estimate - actual`) across every *other* year with a known actual cutoff. The target year is always excluded from its own calibration, even on the rare occasion it already has a known actual_cutoff (e.g. when re-running this against an already-resolved past year) — otherwise the correction would be partly fitted to the answer it's supposed to be predicting.

### Safe grade (`GET /api/estimate/safe`)

The bare cutoff can be misleading — the person right at it may have only gotten in via a strong supplementary application, so plenty of others at that exact grade get rejected. The **safe grade** is a comfortably-likely-to-get-in alternative: the grade cluster reported most often among people who *did* get in (e.g. "low 90s" showing up repeatedly), found by binning each year's raw scraped grades (`backend/data/safe_grades.csv`) and taking the most common bin.

For each year with both a safe grade and an actual cutoff on record, `distance = safe_grade - actual_cutoff` is computed; the average of those distances is added on top of the calibrated cutoff estimate for the current year (`Estimator.estimate_safe_grade`).

## Backtesting

Validated with leave-one-out backtesting — each year predicted using only *prior* years for calibration, compared against what actually happened. This caught a real bug: an earlier unbounded-normal version predicted an impossible 102% cutoff for 2024; switching to Beta cut that year's error from +14.97 to +6.20 and overall MAE from 7.63 to 4.05.

| Year | Actual | Predicted | Error |
|---|---|---|---|
| 2023 | 78.0 | 78.28 | +0.28 |
| 2024 | 85.0 | 91.20 | +6.20 |
| 2025 | 83.0 | 83.34 | +0.34 |

MAE: 2.27, Bias: +2.27 — every single prediction so far has come in at or above the actual cutoff, never below. That's the expected shape of a worst-case model (see Seat math above), not noise: since the underlying seat-math assumptions already lean toward maximum competition, a consistent positive bias is what "working as intended" looks like, whereas a negative bias (underselling how hard a year was) would be the actual red flag.

2026 (the current target year) has no actual_cutoff yet, so it's not backtestable — `GET /api/estimate` shows its live prediction instead.

This runs as `backend/services/backtest.py`, cached to `backend/data/backtest_results.json` and served via `GET /api/backtest` — `backend/app.py` recomputes it hourly in the background (cheap, since it's pure computation with no network calls) so it stays in sync with any edits to the underlying data.

## API summary

| Endpoint | Returns |
|---|---|
| `GET /api/estimate` | `{year, estimated_cutoff}` for the target year |
| `GET /api/estimate/safe` | `{year, estimated_safe_grade}` for the target year |
| `GET /api/history` | `[{year, actual_cutoff, safe_grade}, ...]` — for the frontend chart |
| `GET /api/backtest` | Cached leave-one-out backtest results + summary stats |
| `POST /api/submissions` | Submit a grade report (`{year, csc148, csc165, average}`) for admin review |

## Environment variables

| Variable | Needed for |
|---|---|
| `ADMIN_PASSWORD` | `/admin` login. Unset means admin login always fails. |
| `SECRET_KEY` | Stable admin sessions across restarts (falls back to a random key otherwise). |
| `OPENAI_API_KEY_OTHER` | The scraper's extraction and the admin AI-paste-extract tool. |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Live Reddit scraping (optional — see `backend/scraper/reddit_scraper.py`). |

## School year display

Everywhere a year is shown to a user (chart, tables, the submit-mark and manual-edit selectors), it's spelled out as `YYYY-YY` (e.g. `2024-25`) rather than a bare year, since our internal `year` (Fall-start) convention would otherwise read as a single calendar year. The selectable range runs from `2021` (`backend/utils.MIN_SCHOOL_YEAR`) through whichever school year has most recently started — that upper bound advances automatically every September 1st (`backend/utils.current_school_year_start`), no manual bump needed.

## Known limitations

- Only 3-4 years of calibration data — the correction is itself noisy.
- 2024/2025 cutoffs are partly manual, not IQR-filtered from a large Reddit sample like earlier years.
- Program classification (major vs. DS specialist vs. minor) isn't independently verified.
- `TOTAL_CS_SPOTS = 500` is a constant across all years; may not reflect real year-to-year variation.
- The target year's enrollment counts (forecasted or real-but-still-settling, e.g. before add/drop closes) can shift day to day — the daily background refresh keeps this current, but the live estimate isn't a fixed, final number until that year's enrollment actually settles.
- 2021-2023 have real granular records in `grades.db` (`scraped_grades`) to compute a safe grade from directly; 2024/2025 don't yet, so their `safe_grades.csv` fallback values are themselves *model-estimated* (that year's actual_cutoff + the average distance from 2021-2023) rather than independently observed — the safe-grade calibration is based on just 3 real data points and hasn't been backtested the way the cutoff model was. This resolves itself automatically as more years accumulate real records (via scraping, admin AI-extraction, or approved public submissions).
- `grades.db` is local runtime state (gitignored) — a fresh clone only has the `scraped_grades` seed (auto-migrated on startup); any admin-approved submissions or manual edits made on one deployment don't carry over to another.

## Credits

Enrollment data is sourced from [ICPRplshelp/Enrollment-Data](https://github.com/ICPRplshelp/Enrollment-Data), created for the [UofT Enrollment Tracker](https://github.com/ICPRplshelp/UofT-Enrollment-Tracker), sourced from https://ttb.utoronto.ca/. Per that repo's terms, data is fetched over HTTP rather than via Git, since the author may change hosting at any time.
