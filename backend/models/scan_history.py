"""
ScanHistory model — records every email scan performed by users.
"""

from datetime import datetime
from database import db


class ScanHistory(db.Model):
    """Email scan history table."""

    __tablename__ = "scan_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    email_subject = db.Column(db.String(255), nullable=True)
    email_sender = db.Column(db.String(255), nullable=True)
    email_body_preview = db.Column(db.Text, nullable=True)  # First 500 chars
    prediction = db.Column(db.String(20), nullable=False)   # 'phishing' | 'safe'
    confidence_score = db.Column(db.Float, nullable=False)  # 0.0 – 1.0
    risk_level = db.Column(db.String(20), nullable=False)   # 'low' | 'medium' | 'high' | 'critical'
    urls_found = db.Column(db.Integer, default=0)
    suspicious_urls = db.Column(db.Integer, default=0)
    keywords_flagged = db.Column(db.Text, nullable=True)    # JSON list
    model_used = db.Column(db.String(50), default="ensemble")
    scan_source = db.Column(db.String(30), default="web")   # 'web' | 'extension' | 'api'
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_subject": self.email_subject,
            "email_sender": self.email_sender,
            "email_body_preview": self.email_body_preview,
            "prediction": self.prediction,
            "confidence_score": round(self.confidence_score, 4),
            "risk_level": self.risk_level,
            "urls_found": self.urls_found,
            "suspicious_urls": self.suspicious_urls,
            "keywords_flagged": self.keywords_flagged,
            "model_used": self.model_used,
            "scan_source": self.scan_source,
            "scanned_at": self.scanned_at.isoformat(),
        }

    def __repr__(self):
        return f"<ScanHistory id={self.id} prediction={self.prediction}>"
