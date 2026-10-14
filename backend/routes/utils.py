"""
Route utility helpers — JWT decorator and helpers.
"""

import logging
from functools import wraps

import jwt
from flask import request, jsonify, g

from models.user import User
from database import db
from config import get_config

logger = logging.getLogger(__name__)
cfg = get_config()


def token_required(f):
    """Decorator to protect routes with JWT authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

        if not token:
            return jsonify({"error": "Authentication token required"}), 401

        try:
            payload = jwt.decode(token, cfg.JWT_SECRET_KEY, algorithms=["HS256"])
            user = db.session.get(User, payload["sub"])
            if not user or not user.is_active:
                return jsonify({"error": "Invalid or disabled user"}), 401
            g.current_user = user
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired. Please login again."}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"error": f"Invalid token: {str(e)}"}), 401

        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator to restrict routes to admin users only."""
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        if g.current_user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated


def compute_risk_level(confidence: float, prediction: str) -> str:
    """Map confidence score to risk level string."""
    if prediction != "phishing":
        return "safe"
    if confidence >= 0.90:
        return "critical"
    elif confidence >= 0.75:
        return "high"
    elif confidence >= 0.55:
        return "medium"
    else:
        return "low"
