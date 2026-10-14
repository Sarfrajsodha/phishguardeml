"""
AI Phishing Email Detector — Flask Application Entry Point.

Production-grade REST API server with:
  - JWT Authentication
  - Rate Limiting
  - CORS Protection
  - SQLAlchemy ORM
  - ML Model Integration
  - Comprehensive Logging

Usage:
    python app.py
    FLASK_ENV=production python app.py
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ── Local imports ──────────────────────────────────────────────────────────────
from config import get_config
from database import init_db, db

# ── Setup logging ──────────────────────────────────────────────────────────────
def setup_logging(app: Flask):
    log_level = getattr(logging, app.config["LOG_LEVEL"], logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(log_level)

    # File handler (rotating)
    os.makedirs("logs", exist_ok=True)
    file_handler = RotatingFileHandler("logs/phishing_detector.log", maxBytes=5_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    app.logger.setLevel(log_level)
    app.logger.addHandler(console)
    app.logger.addHandler(file_handler)

    # Root logger
    logging.basicConfig(handlers=[console], level=log_level)


def create_app(config=None) -> Flask:
    """Application factory — creates and configures the Flask app."""
    app = Flask(__name__)

    # ── Config ─────────────────────────────────────────────────────────────────
    cfg = config or get_config()
    app.config.from_object(cfg)

    setup_logging(app)
    logger = logging.getLogger(__name__)

    # ── Extensions ─────────────────────────────────────────────────────────────
    CORS(app, origins=cfg.CORS_ORIGINS, supports_credentials=True)

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[cfg.RATELIMIT_DEFAULT],
        storage_uri=cfg.RATELIMIT_STORAGE_URL,
    )

    # ── Database ───────────────────────────────────────────────────────────────
    init_db(app)

    # ── ML Predictor (lazy-load) ───────────────────────────────────────────────
    from services.ml_predictor import MLPredictor
    predictor = MLPredictor(cfg.MODELS_DIR)
    app.config["ML_PREDICTOR"] = predictor

    if predictor.is_ready():
        logger.info("[App] ML models loaded and ready.")
    else:
        logger.warning("[App] ML models not found. Run training first: python ml/train.py")

    # ── Register Blueprints ────────────────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.scanner import scanner_bp
    from routes.history import history_bp
    from routes.admin import admin_bp
    from routes.model_routes import model_bp
    from routes.gmail import gmail_bp

    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(scanner_bp, url_prefix="/api")
    app.register_blueprint(history_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api")
    app.register_blueprint(model_bp, url_prefix="/api")
    app.register_blueprint(gmail_bp, url_prefix="/api")

    # ── Health Check ───────────────────────────────────────────────────────────
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "version": "1.0.0",
            "models_ready": predictor.is_ready(),
            "models_loaded": list(predictor.models.keys()),
        }), 200

    @app.route("/api/config/public", methods=["GET"])
    def public_config():
        google_client_id = cfg.GOOGLE_CLIENT_ID or ""
        google_configured = bool(
            google_client_id
            and "PLACEHOLDER" not in google_client_id.upper()
            and "YOUR_CLIENT_ID" not in google_client_id.upper()
        )
        return jsonify({
            "google_client_id": google_client_id if google_configured else "",
            "google_configured": google_configured,
        }), 200

    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

    @app.route("/", methods=["GET"])
    def frontend_index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:path>", methods=["GET"])
    def frontend_file(path):
        file_path = os.path.join(frontend_dir, path)
        if os.path.isfile(file_path):
            return send_from_directory(frontend_dir, path)
        return send_from_directory(frontend_dir, "index.html")

    # ── Global Error Handlers ──────────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "details": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized"}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Endpoint not found"}), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({"error": "Rate limit exceeded. Please slow down."}), 429

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    logger.info(f"[App] Flask app created. Environment: {os.getenv('FLASK_ENV', 'development')}")
    return app


# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    print(f"""
╔══════════════════════════════════════════════════════╗
║        AI PHISHING EMAIL DETECTOR — API SERVER       ║
╠══════════════════════════════════════════════════════╣
║  URL  : http://localhost:{port}                        ║
║  Mode : {'Development' if debug else 'Production'}                        ║
╚══════════════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=debug)
