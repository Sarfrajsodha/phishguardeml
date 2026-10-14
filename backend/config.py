"""
Configuration module for AI Phishing Email Detector.
Handles all environment-based configuration with sensible defaults.
"""

import os
from datetime import timedelta

from dotenv import load_dotenv


load_dotenv(os.path.join(os.path.abspath(os.path.dirname(__file__)), ".env"), override=True)


class Config:
    """Base configuration class."""

    # ── Flask ──────────────────────────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "phish-detect-super-secret-key-2024")
    DEBUG = False
    TESTING = False

    # ── Database ───────────────────────────────────────────────────────────
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    _DATABASE_URL = os.getenv("DATABASE_URL")
    if _DATABASE_URL and _DATABASE_URL.startswith("sqlite:///"):
        _sqlite_path = _DATABASE_URL.replace("sqlite:///", "", 1)
        SQLALCHEMY_DATABASE_URI = (
            _DATABASE_URL
            if os.path.isabs(_sqlite_path)
            else f"sqlite:///{os.path.join(BASE_DIR, _sqlite_path)}"
        )
    else:
        SQLALCHEMY_DATABASE_URI = _DATABASE_URL or f"sqlite:///{os.path.join(BASE_DIR, 'phishing_detector.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── JWT ────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-phish-secret-2024")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    # ── Rate Limiting ──────────────────────────────────────────────────────
    RATELIMIT_DEFAULT = "100 per hour"
    RATELIMIT_STORAGE_URL = "memory://"

    # ── CORS ───────────────────────────────────────────────────────────────
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    # ── ML Models ─────────────────────────────────────────────────────────
    MODELS_DIR = os.path.join(BASE_DIR, "ml", "models")

    # ── Upload ─────────────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max upload
    ALLOWED_EXTENSIONS = {"eml", "txt"}

    # ── Logging ────────────────────────────────────────────────────────────
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # ── Google OAuth 2.0 ───────────────────────────────────────────────────
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/api/gmail/oauth/callback")
    # Format: YOUR_CLIENT_ID.apps.googleusercontent.com
    # Get from: https://console.cloud.google.com/apis/credentials


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    RATELIMIT_DEFAULT = "50 per hour"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config() -> Config:
    """Return the config object based on ENV variable."""
    env = os.getenv("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
