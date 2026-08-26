# API endpoints — /api/estimate, /api/estimate/safe, /api/history, /api/backtest, /api/submissions.
from flask import Blueprint, jsonify, request

from backend.services.backtest import load_backtest_results
from backend.services.estimate_service import get_history, get_latest_estimate, get_latest_safe_grade_estimate
from backend.services.submissions import create_submission
from backend.utils import MIN_SCHOOL_YEAR, current_school_year_start

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/estimate", methods=["GET"])
def estimate():
    try:
        result = get_latest_estimate()
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


@api_bp.route("/estimate/safe", methods=["GET"])
def estimate_safe():
    """The "safe" grade — comfortably likely to get in, not just the bare
    (possibly supplementary-application-skewed) cutoff.
    """
    try:
        result = get_latest_safe_grade_estimate()
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


@api_bp.route("/history", methods=["GET"])
def history():
    """Per-year actual cutoff + safe grade, for the frontend chart."""
    try:
        result = get_history()
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


@api_bp.route("/backtest", methods=["GET"])
def backtest():
    """Cached leave-one-out backtest results (see backend/services/backtest.py) —
    recomputed periodically in the background, not on each request.
    """
    try:
        result = load_backtest_results()
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


@api_bp.route("/submissions", methods=["POST"])
def submit_grade():
    """Submit a grade report for admin review — never touches the live
    estimate directly (see backend/api/admin_routes.py for the approval flow).
    """
    body = request.get_json(silent=True) or {}

    try:
        year = int(body["year"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "`year` is required and must be an integer"}), 400

    max_year = current_school_year_start()
    if not (MIN_SCHOOL_YEAR <= year <= max_year):
        return jsonify({"error": f"`year` must be between {MIN_SCHOOL_YEAR} and {max_year}"}), 400

    def parse_grade(field):
        value = body.get(field)
        if value in (None, ""):
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"`{field}` must be a number")
        if not (0 <= value <= 100):
            raise ValueError(f"`{field}` must be between 0 and 100")
        return value

    try:
        csc148 = parse_grade("csc148")
        csc165 = parse_grade("csc165")
        average = parse_grade("average")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        submission_id = create_submission(year, csc148, csc165, average)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": submission_id, "status": "pending"}), 201
