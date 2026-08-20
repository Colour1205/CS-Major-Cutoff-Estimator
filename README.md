# CS Major Cutoff Estimator

Estimates the predicted UofT CS major cutoff average (based on CSC148 and CSC165) using historical data and current enrollment counts.

## Year convention

Throughout this project (config, data files, code), a `year` labels an academic year by its **Fall start year**, matching `ENROLLMENT_SESSIONS` in `backend/config.py`. For example, `year = 2025` means **Fall 2025 – Winter 2026**: CSC148 is taken in Fall 2025, CSC165 in Winter 2026, and the CS major admission decision for that cohort is released in summer 2026 — the year *after* the label.

## Credits

Enrollment data is sourced from [ICPRplshelp/Enrollment-Data](https://github.com/ICPRplshelp/Enrollment-Data), created for the [UofT Enrollment Tracker](https://github.com/ICPRplshelp/UofT-Enrollment-Tracker). All enrollment data in that repo is maintained by its author, sourced from https://ttb.utoronto.ca/. Per that repo's terms, we fetch data over HTTP (raw file URLs) rather than via Git, since the author may change hosting at any time.
