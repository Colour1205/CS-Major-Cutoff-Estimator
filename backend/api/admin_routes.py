# Admin-only site: approve/reject submissions, manually edit year data, and
# an AI paste-and-extract tool. A separate area from the public frontend,
# gated behind session auth (see admin_required) rather than linked from it.
import hmac
import os
from collections import Counter
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from backend.services import manual_data, submissions
from backend.services.ai_extraction import extract_reports_from_text
from backend.services.backtest import write_backtest_results
from backend.services.estimate_service import _load_csv_by_year, _load_overrides, get_history
from backend.config import ENROLLMENT_DATA_CSV_PATH, MIN_RECORDS_TO_OVERRIDE
from backend.utils import MIN_SCHOOL_YEAR, current_school_year_start

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _check_password(password: str) -> bool:
    expected = os.environ.get("ADMIN_PASSWORD")
    if not expected:
        return False
    return hmac.compare_digest(password, expected)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped


def _refresh_estimate() -> None:
    """Every admin data mutation should be reflected immediately, not wait
    for the hourly background refresh — /api/estimate and /api/history are
    already always computed live on request, but backtest_results.json is
    cached, so that's the one thing that needs an explicit recompute here.
    """
    write_backtest_results()


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if _check_password(request.form.get("password", "")):
            session["is_admin"] = True
            return redirect(url_for("admin.dashboard"))
        error = "Wrong password" if os.environ.get("ADMIN_PASSWORD") else "ADMIN_PASSWORD is not set on the server"
    return render_template("admin_login.html", error=error)


@admin_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin.login"))


def _format_timestamp(iso_string: str) -> str:
    try:
        return datetime.fromisoformat(iso_string).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return iso_string


@admin_bp.route("/", methods=["GET"])
@admin_required
def dashboard():
    all_submissions = submissions.list_submissions()
    pending_submissions = [s for s in all_submissions if s["status"] == "pending"]

    # How many *currently pending* submissions share each ip_hash -- a
    # "is there an active spam burst right now" signal, not a lifetime
    # tally, so it naturally drops to 0 for a source once everything it
    # submitted has been approved/rejected.
    source_counts = Counter(s["ip_hash"] for s in pending_submissions if s.get("ip_hash"))

    pending = []
    for s in pending_submissions:
        pending.append({
            **s,
            "submitted_at": _format_timestamp(s["submitted_at"]),
            "same_source_count": source_counts.get(s.get("ip_hash"), 1) - 1,
        })

    approved_by_year = submissions.get_approved_grades_by_year()
    overrides = _load_overrides()
    year_rows = [
        {"year": row["year"], "actual_cutoff": row["actual_cutoff"], "safe_grade": row["safe_grade"],
         "record_count": len(approved_by_year.get(row["year"], [])),
         "overridden_fields": sorted(overrides.get(row["year"], set()))}
        for row in get_history()
    ]

    enrollment_years = sorted(_load_csv_by_year(ENROLLMENT_DATA_CSV_PATH).keys())
    server_info = {
        "enrollment_years": enrollment_years,
        "total_submissions": len(all_submissions),
        "pending_count": len(pending),
        "approved_count": len([s for s in all_submissions if s["status"] == "approved"]),
        "rejected_count": len([s for s in all_submissions if s["status"] == "rejected"]),
        "scraped_grade_count": len(submissions.list_scraped_grades()),
    }

    return render_template(
        "admin_dashboard.html",
        pending=pending,
        year_rows=year_rows,
        server_info=server_info,
        min_school_year=MIN_SCHOOL_YEAR,
        max_school_year=current_school_year_start(),
        min_records_to_override=MIN_RECORDS_TO_OVERRIDE,
    )


@admin_bp.route("/pending_count", methods=["GET"])
@admin_required
def pending_count():
    """Polled by the dashboard's auto-refresh JS so a new submission shows
    up without the admin needing to manually reload the page.
    """
    count = len(submissions.list_submissions(status="pending"))
    return jsonify({"pending_count": count})


@admin_bp.route("/submissions/<int:submission_id>/approve", methods=["POST"])
@admin_required
def approve_submission(submission_id):
    submissions.update_submission_status(submission_id, "approved")
    _refresh_estimate()
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/submissions/<int:submission_id>/reject", methods=["POST"])
@admin_required
def reject_submission(submission_id):
    submissions.update_submission_status(submission_id, "rejected")
    _refresh_estimate()
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/data/manual", methods=["POST"])
@admin_required
def manual_edit():
    year = int(request.form["year"])
    actual_cutoff = request.form.get("actual_cutoff", "").strip()
    safe_grade = request.form.get("safe_grade", "").strip()
    force_override = request.form.get("force_override") == "on"

    if actual_cutoff:
        manual_data.set_actual_cutoff(year, float(actual_cutoff))
        if force_override:
            manual_data.set_override(year, "actual_cutoff")
    if safe_grade:
        manual_data.set_safe_grade(year, float(safe_grade))
        if force_override:
            manual_data.set_override(year, "safe_grade")

    _refresh_estimate()
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/data/manual/<int:year>/revert", methods=["POST"])
@admin_required
def revert_override(year):
    """Drop a year's force-override flags -- it goes back to being computed
    from grades.db records once it has enough of them (see
    estimate_service._effective_values), or the manual-edit CSV value
    below that threshold.
    """
    manual_data.clear_override(year)
    _refresh_estimate()
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/data/extract", methods=["POST"])
@admin_required
def extract():
    """Paste raw text -> OpenAI extracts structured reports -> return as
    JSON for the admin to review/edit before confirming (see /data/extract/confirm).
    Doesn't touch the database yet.
    """
    text = request.json.get("text", "") if request.is_json else request.form.get("text", "")
    try:
        raw_reports = extract_reports_from_text(text)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    reports = []
    for r in raw_reports:
        decision_year = r.get("decision_year")
        reports.append({
            "year": decision_year - 1 if decision_year is not None else None,
            "csc148": r.get("csc148"),
            "csc165": r.get("csc165"),
            "average": r.get("average"),
            "program": r.get("program"),
        })
    return jsonify({"reports": reports})


@admin_bp.route("/data/extract/confirm", methods=["POST"])
@admin_required
def extract_confirm():
    """Insert the (admin-reviewed, possibly hand-edited) extracted reports
    as already-approved submissions -- the admin already vetted them.
    """
    reports = request.json.get("reports", [])
    inserted = 0
    for r in reports:
        if r.get("program") not in (None, "cs_major"):
            continue  # admin left a non-major report in the list -- skip it
        if r.get("year") is None:
            continue
        submissions.create_approved_submission(
            year=int(r["year"]),
            csc148=r.get("csc148"),
            csc165=r.get("csc165"),
            average=r.get("average"),
        )
        inserted += 1

    _refresh_estimate()
    return jsonify({"inserted": inserted})
