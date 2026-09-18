import logging
from flask import Blueprint, request, jsonify
from backend.routes.auth import get_authenticated_user_id
from backend.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)

recommendations_bp = Blueprint('recommendations', __name__)


@recommendations_bp.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """
    Retrieve personalized adaptive recommendations for the authenticated student.
    Recommendations are generated dynamically using MySQL performance metrics,
    quiz attempts, learning sessions, and cognitive style preferences.
    """
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        result = RecommendationService.generate_recommendations_for_user(user_id)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error retrieving recommendations for user {user_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@recommendations_bp.route('/api/recommendations/generate', methods=['POST'])
def generate_recommendations():
    """
    Explicitly trigger recalculation and regeneration of recommendations for the authenticated student.
    """
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        result = RecommendationService.generate_recommendations_for_user(user_id)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error generating recommendations for user {user_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@recommendations_bp.route('/api/recommendations/train', methods=['POST'])
def train_recommendation_model():
    """
    Trigger training or retraining of the XGBoost model on real MySQL student performance records.
    If sample threshold is not reached, reports status and maintains safe deterministic baseline.
    """
    data = request.get_json() or {}
    min_samples = data.get("min_samples", 20)

    try:
        result = RecommendationService.train_model(min_samples=min_samples)
        status_code = 200 if result.get("status") == "success" else 200
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Error training recommendation model: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@recommendations_bp.route('/api/recommendations/status', methods=['GET'])
def recommendation_model_status():
    """
    Get current XGBoost model status, features, and active recommendation engine info.
    """
    try:
        status_info = RecommendationService.get_model_status()
        return jsonify({"status": "success", "data": status_info}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
