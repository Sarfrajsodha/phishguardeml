"""
ThreatLog & ModelMetrics models.
ThreatLog stores detailed threat intelligence per scan.
ModelMetrics stores ML model performance metrics.
"""

from datetime import datetime
from database import db


class ThreatLog(db.Model):
    """Detailed threat intelligence for phishing detections."""

    __tablename__ = "threat_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scan_id = db.Column(db.Integer, db.ForeignKey("scan_history.id"), nullable=True)
    threat_type = db.Column(db.String(50), nullable=False)   # 'url_spoofing' | 'domain_spoof' | ...
    threat_details = db.Column(db.Text, nullable=True)        # JSON with details
    severity = db.Column(db.String(20), default="medium")    # 'low' | 'medium' | 'high' | 'critical'
    flagged_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "scan_id": self.scan_id,
            "threat_type": self.threat_type,
            "threat_details": self.threat_details,
            "severity": self.severity,
            "flagged_at": self.flagged_at.isoformat(),
        }


class ModelMetrics(db.Model):
    """Stores ML model training and evaluation metrics."""

    __tablename__ = "model_metrics"

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False)
    accuracy = db.Column(db.Float, nullable=True)
    precision = db.Column(db.Float, nullable=True)
    recall = db.Column(db.Float, nullable=True)
    f1_score = db.Column(db.Float, nullable=True)
    training_samples = db.Column(db.Integer, nullable=True)
    training_duration_sec = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=False)
    trained_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "model_name": self.model_name,
            "accuracy": round(self.accuracy, 4) if self.accuracy else None,
            "precision": round(self.precision, 4) if self.precision else None,
            "recall": round(self.recall, 4) if self.recall else None,
            "f1_score": round(self.f1_score, 4) if self.f1_score else None,
            "training_samples": self.training_samples,
            "training_duration_sec": self.training_duration_sec,
            "is_active": self.is_active,
            "trained_at": self.trained_at.isoformat(),
        }
