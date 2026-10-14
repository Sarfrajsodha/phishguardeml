"""
Database initialization module.
Uses Flask-SQLAlchemy with SQLite for persistence.
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

db = SQLAlchemy()


def _ensure_user_oauth_columns():
    """Add OAuth columns when upgrading an existing SQLite database."""
    inspector = inspect(db.engine)
    if not inspector.has_table("users"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    oauth_columns = {
        "google_id": "VARCHAR(255)",
        "auth_provider": "VARCHAR(20)",
        "profile_picture": "VARCHAR(500)",
        "gmail_refresh_token": "TEXT",
        "gmail_access_token": "TEXT",
        "gmail_token_expiry": "DATETIME",
    }

    with db.engine.begin() as connection:
        for column_name, column_type in oauth_columns.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))


def init_db(app):
    """Initialize the database with the Flask application."""
    db.init_app(app)
    with app.app_context():
        # Import models so SQLAlchemy registers their table metadata
        from models.user import User  # noqa: F401
        from models.gmail_oauth_state import GmailOAuthState  # noqa: F401
        from models.scan_history import ScanHistory  # noqa: F401
        from models.threat_log import ThreatLog, ModelMetrics  # noqa: F401
        db.create_all()
        _ensure_user_oauth_columns()
        print("[DB] Database tables created/verified.")
