"""
Model Training Routes — /train-model endpoint.
Triggers ML model retraining via API.
"""

import json
import logging
import threading
import time

from flask import Blueprint, request, jsonify, current_app

from database import db
from models.threat_log import ModelMetrics
from routes.utils import admin_required

logger = logging.getLogger(__name__)
model_bp = Blueprint("model_routes", __name__)

training_status = {"running": False, "last_run": None, "last_result": None}


@model_bp.route("/train-model", methods=["POST"])
@admin_required
def train_model():
    """
    Trigger ML model retraining.
    Runs in background thread to avoid request timeout.
    """
    if training_status["running"]:
        return jsonify({"error": "Training already in progress. Please wait."}), 409

    def _run_training():
        training_status["running"] = True
        training_status["last_run"] = time.time()
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
            from ml.train import generate_dataset, train_models

            df = generate_dataset()
            metrics = train_models(df)
            training_status["last_result"] = {"success": True, "metrics": metrics}

            # Save metrics to DB
            with current_app.app_context():
                for model_name, m in metrics.items():
                    metric = ModelMetrics(
                        model_name=model_name,
                        accuracy=m["accuracy"],
                        precision=m["precision"],
                        recall=m["recall"],
                        f1_score=m["f1_score"],
                        training_samples=m["training_samples"],
                        training_duration_sec=m["training_duration_sec"],
                        is_active=True,
                    )
                    db.session.add(metric)
                db.session.commit()

            # Reload predictor
            predictor = current_app.config.get("ML_PREDICTOR")
            if predictor:
                predictor.reload()
                logger.info("[TrainModel] Models reloaded into predictor.")

        except Exception as e:
            logger.error(f"[TrainModel] Training failed: {e}")
            training_status["last_result"] = {"success": False, "error": str(e)}
        finally:
            training_status["running"] = False

    thread = threading.Thread(target=_run_training, daemon=True)
    thread.start()

    return jsonify({
        "message": "Model training started in background. Check /train-status for updates.",
        "status": "running",
    }), 202


@model_bp.route("/train-status", methods=["GET"])
@admin_required
def train_status():
    """Check status of the last training run."""
    return jsonify({
        "running": training_status["running"],
        "last_run": training_status["last_run"],
        "last_result": training_status["last_result"],
    }), 200


@model_bp.route("/model-metrics", methods=["GET"])
def get_metrics():
    """Return latest metrics for each model (public endpoint)."""
    metrics = ModelMetrics.query.order_by(ModelMetrics.trained_at.desc()).limit(10).all()
    return jsonify({"metrics": [m.to_dict() for m in metrics]}), 200
