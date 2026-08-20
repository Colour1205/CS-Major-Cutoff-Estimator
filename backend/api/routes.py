# API endpoints — /api/estimate, /api/history.
from flask import Blueprint, jsonify

from backend.services.cutoff_calculator import get_latest_estimate

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/estimate", methods=["GET"])
def estimate():
    try:
        result = get_latest_estimate()
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(result)
