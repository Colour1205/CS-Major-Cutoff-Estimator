# API endpoints — /api/estimate, /api/estimate/safe, /api/history, /api/backtest.
from flask import Blueprint, jsonify

from backend.services.backtest import load_backtest_results
from backend.services.estimate_service import get_history, get_latest_estimate, get_latest_safe_grade_estimate

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
