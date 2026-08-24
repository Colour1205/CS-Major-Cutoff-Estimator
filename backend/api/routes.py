# API endpoints — /api/estimate, /api/estimate/safe.
from flask import Blueprint, jsonify

from backend.services.cutoff_calculator import get_latest_estimate, get_latest_safe_grade_estimate

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
