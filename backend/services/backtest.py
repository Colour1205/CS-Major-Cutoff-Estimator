# Leave-one-out backtest of the cutoff estimator: each year's prediction
# uses only prior years for calibration, never its own or future years'
# actual data. Results are written to disk so the API can serve them
# without recomputing on every request.
import json
import threading
import time
from pathlib import Path

from backend.config import BACKTEST_RESULTS_JSON_PATH
from backend.models.estimator import Estimator
from backend.services.estimate_service import load_merged_data


def run_backtest() -> dict:
    """Predict every year (except the first, which has no prior years to
    calibrate from) using only years before it, and compare against what
    actually happened.

    Returns {"results": [{"year", "actual", "predicted", "error"}, ...],
             "summary": {"n", "mae", "rmse", "bias"}}.
    """
    data = load_merged_data()
    years = sorted(data.keys())

    results = []
    errors = []
    for i, year in enumerate(years):
        if i == 0:
            continue  # no prior years to calibrate from

        actual_cutoff = data[year].get("actual_cutoff")
        if actual_cutoff in (None, ""):
            continue  # not resolved yet (e.g. the current target year) -- can't backtest

        subset = {y: dict(data[y]) for y in years[: i + 1]}
        predicted = Estimator(subset).estimate_cutoff()
        actual = float(actual_cutoff)
        error = predicted - actual

        errors.append(error)
        results.append({
            "year": year,
            "actual": actual,
            "predicted": round(predicted, 2),
            "error": round(error, 2),
        })

    summary = {}
    if errors:
        n = len(errors)
        summary = {
            "n": n,
            "mae": round(sum(abs(e) for e in errors) / n, 2),
            "rmse": round((sum(e ** 2 for e in errors) / n) ** 0.5, 2),
            "bias": round(sum(errors) / n, 2),
        }

    return {"results": results, "summary": summary}


def write_backtest_results(path: str = BACKTEST_RESULTS_JSON_PATH) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(run_backtest(), f, indent=2)


def load_backtest_results(path: str = BACKTEST_RESULTS_JSON_PATH) -> dict:
    """Read cached backtest results, computing them once if they don't exist yet."""
    out_path = Path(path)
    if not out_path.exists():
        write_backtest_results(path)
    with open(out_path) as f:
        return json.load(f)


def start_background_backtest_refresh(interval_seconds: int = 3600) -> None:
    """Start a daemon thread that recomputes backtest_results.json
    periodically — cheap (pure computation, no network calls), so this runs
    more often than the enrollment fetch, picking up any edits to
    historical_averages.csv/safe_grades.csv or newly-arrived enrollment data.
    """
    def loop():
        while True:
            try:
                write_backtest_results()
            except Exception as e:
                print(f"[backtest refresh] failed: {e}")
            time.sleep(interval_seconds)

    threading.Thread(target=loop, daemon=True).start()


if __name__ == "__main__":
    write_backtest_results()
    print(json.dumps(load_backtest_results(), indent=2))
