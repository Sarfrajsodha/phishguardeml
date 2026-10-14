"""
History Routes — /history endpoint for user scan history.
"""

import logging
from flask import Blueprint, request, jsonify, g

from database import db
from models.scan_history import ScanHistory
from routes.utils import token_required

logger = logging.getLogger(__name__)
history_bp = Blueprint("history", __name__)


@history_bp.route("/history", methods=["GET"])
@token_required
def get_history():
    """
    Return paginated scan history for the authenticated user.
    Query params: page (default 1), per_page (default 20), filter (all|phishing|safe)
    """
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    filter_type = request.args.get("filter", "all")

    query = ScanHistory.query.filter_by(user_id=g.current_user.id)

    if filter_type == "phishing":
        query = query.filter_by(prediction="phishing")
    elif filter_type == "safe":
        query = query.filter_by(prediction="safe")

    query = query.order_by(ScanHistory.scanned_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "scans": [scan.to_dict() for scan in pagination.items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }), 200


@history_bp.route("/history/<int:scan_id>", methods=["GET"])
@token_required
def get_scan_detail(scan_id: int):
    """Return details of a specific scan."""
    scan = ScanHistory.query.filter_by(id=scan_id, user_id=g.current_user.id).first()
    if not scan:
        return jsonify({"error": "Scan not found"}), 404
    return jsonify({"scan": scan.to_dict()}), 200


@history_bp.route("/history/<int:scan_id>", methods=["DELETE"])
@token_required
def delete_scan(scan_id: int):
    """Delete a specific scan record."""
    scan = ScanHistory.query.filter_by(id=scan_id, user_id=g.current_user.id).first()
    if not scan:
        return jsonify({"error": "Scan not found"}), 404
    db.session.delete(scan)
    db.session.commit()
    return jsonify({"message": "Scan deleted"}), 200


@history_bp.route("/history/stats", methods=["GET"])
@token_required
def get_stats():
    """Return aggregated scan statistics for the current user's dashboard."""
    user_id = g.current_user.id

    total = ScanHistory.query.filter_by(user_id=user_id).count()
    phishing = ScanHistory.query.filter_by(user_id=user_id, prediction="phishing").count()
    safe = ScanHistory.query.filter_by(user_id=user_id, prediction="safe").count()

    # Risk level distribution
    risk_levels = {}
    for level in ["safe", "low", "medium", "high", "critical"]:
        risk_levels[level] = ScanHistory.query.filter_by(
            user_id=user_id, risk_level=level
        ).count()

    # Recent 7 scans
    recent = (
        ScanHistory.query.filter_by(user_id=user_id)
        .order_by(ScanHistory.scanned_at.desc())
        .limit(7)
        .all()
    )

    # Average confidence
    from sqlalchemy import func
    avg_conf = db.session.query(func.avg(ScanHistory.confidence_score)).filter_by(
        user_id=user_id
    ).scalar() or 0.0

    return jsonify({
        "total_scans": total,
        "phishing_count": phishing,
        "safe_count": safe,
        "phishing_rate": round(phishing / total * 100, 1) if total > 0 else 0,
        "average_confidence": round(avg_conf, 4),
        "risk_distribution": risk_levels,
        "recent_scans": [s.to_dict() for s in recent],
    }), 200
