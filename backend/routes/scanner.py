"""
Scanner Routes — /scan-email endpoint.
Core phishing detection pipeline integrating NLP + ML + URL analysis.
"""

import json
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, g, current_app

from database import db
from models.scan_history import ScanHistory
from models.threat_log import ThreatLog
from services.nlp_processor import NLPProcessor
from services.url_scanner import URLScanner
from services.email_parser import EmailParser
from routes.utils import token_required, compute_risk_level

logger = logging.getLogger(__name__)
scanner_bp = Blueprint("scanner", __name__)

# ── Shared service instances ───────────────────────────────────────────────────
nlp = NLPProcessor()
url_scanner = URLScanner()
email_parser = EmailParser()


# ── POST /scan-email ───────────────────────────────────────────────────────────

@scanner_bp.route("/scan-email", methods=["POST"])
@token_required
def scan_email():
    """
    Analyze an email for phishing.

    Accepts:
      - JSON body: { subject, sender, body, model }
      - Multipart file upload: .eml file field named 'file'

    Returns comprehensive phishing analysis.
    """
    predictor = current_app.config.get("ML_PREDICTOR")

    # ── Parse Input ────────────────────────────────────────────────────────────
    if request.is_json:
        data = request.get_json(silent=True) or {}
        subject = str(data.get("subject", "")).strip()
        sender = str(data.get("sender", "")).strip()
        body = str(data.get("body", "")).strip()
        model_name = str(data.get("model", "ensemble")).strip()
        scan_source = "api"
    elif request.files.get("file"):
        # .eml file upload
        uploaded_file = request.files["file"]
        raw_bytes = uploaded_file.read()
        parsed = email_parser.parse_eml_bytes(raw_bytes)
        subject = parsed.get("subject", "")
        sender = parsed.get("sender", "")
        body = parsed.get("body", "") or parsed.get("html_body", "")
        model_name = request.form.get("model", "ensemble")
        scan_source = "upload"
    else:
        data = request.form.to_dict()
        subject = str(data.get("subject", "")).strip()
        sender = str(data.get("sender", "")).strip()
        body = str(data.get("body", "")).strip()
        model_name = str(data.get("model", "ensemble")).strip()
        scan_source = "web"

    if not body:
        return jsonify({"error": "Email body is required"}), 400

    # ── NLP Processing ─────────────────────────────────────────────────────────
    full_text = f"{subject} {sender} {body}".strip()
    nlp_result = nlp.process(full_text)
    processed_text = nlp_result["processed_text"]

    # ── URL Analysis ───────────────────────────────────────────────────────────
    url_result = url_scanner.analyze_text(body)

    # ── ML Prediction ─────────────────────────────────────────────────────────
    if predictor and predictor.is_ready():
        ml_result = predictor.predict(processed_text, model_name)
    else:
        # Heuristic fallback when models aren't trained yet
        ml_result = _heuristic_predict(nlp_result, url_result)

    prediction = ml_result["prediction"]
    confidence = ml_result["confidence"]

    # Boost confidence if strong URL signals
    if url_result["suspicious_count"] > 0 and prediction == "phishing":
        boost = min(0.1 * url_result["suspicious_count"], 0.15)
        confidence = min(confidence + boost, 0.99)
    elif url_result["suspicious_count"] > 2:
        # Override to phishing if many bad URLs even if ML says safe
        prediction = "phishing"
        confidence = max(confidence, 0.75)

    risk_level = compute_risk_level(confidence, prediction)

    # ── Build Response ─────────────────────────────────────────────────────────
    result = {
        "prediction": prediction,
        "confidence": round(confidence, 4),
        "confidence_percent": round(confidence * 100, 1),
        "risk_level": risk_level,
        "model_used": ml_result.get("model_used", "ensemble"),
        "model_breakdown": ml_result.get("model_breakdown", {}),
        "nlp_analysis": {
            "token_count": nlp_result["token_count"],
            "phishing_keywords": nlp_result["phishing_keywords"],
            "keyword_count": nlp_result["keyword_count"],
            "urgency_score": nlp_result["urgency_score"],
            "has_urgent_language": nlp_result["has_urgent_language"],
            "exclamation_count": nlp_result["exclamation_count"],
            "caps_ratio": nlp_result["caps_ratio"],
            "has_html": nlp_result["has_html"],
        },
        "url_analysis": {
            "total_urls": url_result["total_urls"],
            "suspicious_count": url_result["suspicious_count"],
            "has_http_only": url_result["has_http_only"],
            "has_shortened": url_result["has_shortened"],
            "has_suspicious_tld": url_result["has_suspicious_tld"],
            "urls": url_result["urls"][:10],  # Limit to first 10
        },
        "email_metadata": {
            "subject": subject,
            "sender": sender,
        },
        "scan_timestamp": datetime.utcnow().isoformat(),
    }

    # ── Save to Database ───────────────────────────────────────────────────────
    scan = ScanHistory(
        user_id=g.current_user.id,
        email_subject=subject[:255] if subject else None,
        email_sender=sender[:255] if sender else None,
        email_body_preview=body[:500],
        prediction=prediction,
        confidence_score=confidence,
        risk_level=risk_level,
        urls_found=url_result["total_urls"],
        suspicious_urls=url_result["suspicious_count"],
        keywords_flagged=json.dumps(nlp_result["phishing_keywords"]),
        model_used=ml_result.get("model_used", "ensemble"),
        scan_source=scan_source,
    )
    db.session.add(scan)

    # Log threats if phishing detected
    if prediction == "phishing":
        threats = _build_threat_logs(g.current_user.id, scan, nlp_result, url_result)
        for threat in threats:
            db.session.add(threat)

    db.session.commit()

    result["scan_id"] = scan.id
    return jsonify(result), 200


def _heuristic_predict(nlp_result: dict, url_result: dict) -> dict:
    """Fallback heuristic scoring when ML models are not available."""
    score = 0

    # Keyword signals
    score += min(nlp_result["urgency_score"] * 0.05, 0.35)

    # URL signals
    if url_result["suspicious_count"] > 0:
        score += min(url_result["suspicious_count"] * 0.12, 0.35)
    if url_result["has_http_only"]:
        score += 0.08
    if url_result["has_shortened"]:
        score += 0.10

    # Text signals
    if nlp_result["caps_ratio"] > 0.3:
        score += 0.08
    if nlp_result["exclamation_count"] > 3:
        score += 0.05

    score = min(score, 0.99)
    prediction = "phishing" if score >= 0.45 else "safe"

    return {
        "prediction": prediction,
        "confidence": round(score, 4),
        "model_used": "heuristic",
        "model_breakdown": {"heuristic": {"prediction": prediction, "confidence": round(score, 4)}},
        "error": None,
    }


def _build_threat_logs(user_id: int, scan, nlp_result: dict, url_result: dict) -> list:
    """Create ThreatLog entries for detected threats."""
    threats = []

    if nlp_result["phishing_keywords"]:
        threats.append(ThreatLog(
            user_id=user_id,
            scan_id=scan.id,
            threat_type="phishing_keywords",
            threat_details=json.dumps({"keywords": nlp_result["phishing_keywords"]}),
            severity="high" if nlp_result["urgency_score"] > 8 else "medium",
        ))

    for url_info in url_result["urls"]:
        if url_info.get("is_suspicious"):
            threats.append(ThreatLog(
                user_id=user_id,
                scan_id=scan.id,
                threat_type="suspicious_url",
                threat_details=json.dumps({
                    "url": url_info["url"],
                    "flags": url_info.get("flags", []),
                    "risk_score": url_info.get("risk_score", 0),
                }),
                severity="high" if url_info.get("risk_score", 0) > 8 else "medium",
            ))

    return threats
