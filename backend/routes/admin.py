"""
Admin Routes — statistics, user management, and model metrics.
Requires admin role.
"""

import logging
from flask import Blueprint, request, jsonify

from database import db
from models.user import User
from models.scan_history import ScanHistory
from models.threat_log import ThreatLog, ModelMetrics
from routes.utils import admin_required, token_required

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/stats", methods=["GET"])
@admin_required
def admin_stats():
    """Global platform statistics for admin dashboard."""
    total_users = User.query.count()
    total_scans = ScanHistory.query.count()
    phishing_scans = ScanHistory.query.filter_by(prediction="phishing").count()
    safe_scans = ScanHistory.query.filter_by(prediction="safe").count()
    total_threats = ThreatLog.query.count()

    # Recent activity (last 10 scans across all users)
    recent_scans = (
        ScanHistory.query.order_by(ScanHistory.scanned_at.desc()).limit(10).all()
    )

    return jsonify({
        "platform": {
            "total_users": total_users,
            "total_scans": total_scans,
            "phishing_detected": phishing_scans,
            "safe_emails": safe_scans,
            "total_threats": total_threats,
            "phishing_rate": round(phishing_scans / total_scans * 100, 1) if total_scans > 0 else 0,
        },
        "recent_scans": [s.to_dict() for s in recent_scans],
    }), 200


@admin_bp.route("/admin/users", methods=["GET"])
@admin_required
def list_users():
    """List all users."""
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"users": [u.to_dict() for u in users]}), 200


@admin_bp.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id: int):
    """Enable/disable a user account."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({"message": f"User {'enabled' if user.is_active else 'disabled'}", "user": user.to_dict()}), 200


@admin_bp.route("/admin/model-metrics", methods=["GET"])
@admin_required
def model_metrics():
    """Return all model training metrics."""
    metrics = ModelMetrics.query.order_by(ModelMetrics.trained_at.desc()).all()
    return jsonify({"metrics": [m.to_dict() for m in metrics]}), 200


@admin_bp.route("/admin/threats", methods=["GET"])
@admin_required
def list_threats():
    """List recent threat logs across all users."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    query = ThreatLog.query.order_by(ThreatLog.flagged_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "threats": [t.to_dict() for t in pagination.items],
        "total": pagination.total,
    }), 200
