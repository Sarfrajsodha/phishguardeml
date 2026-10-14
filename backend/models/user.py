"""
User model — stores registered users with hashed passwords.
"""

from datetime import datetime
from database import db
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    """User account table."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)  # Nullable for OAuth users
    role = db.Column(db.String(20), default="user")  # 'user' | 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # OAuth fields
    google_id = db.Column(db.String(255), unique=True, nullable=True)  # Google sub claim
    auth_provider = db.Column(db.String(20), nullable=True)  # 'google' | 'email' | None for legacy
    profile_picture = db.Column(db.String(500), nullable=True)  # Avatar URL from OAuth provider
    gmail_refresh_token = db.Column(db.Text, nullable=True)  # Server-side only
    gmail_access_token = db.Column(db.Text, nullable=True)  # Server-side only
    gmail_token_expiry = db.Column(db.DateTime, nullable=True)

    # Relationships
    scan_history = db.relationship(
        "ScanHistory", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    threat_logs = db.relationship(
        "ThreatLog", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password: str):
        """Hash and store the password using pbkdf2:sha256 (compatible with all Python builds)."""
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        """Serialize user to dictionary (safe, no password)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_active": self.is_active,
            "auth_provider": self.auth_provider,
            "profile_picture": self.profile_picture,
        }

    def __repr__(self):
        return f"<User {self.username}>"
