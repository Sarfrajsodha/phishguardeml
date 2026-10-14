"""
Authentication Routes.
Handles /register and /login endpoints with JWT token generation.
Supports both email/password and Google OAuth 2.0 authentication.
"""

import logging
from datetime import datetime, timezone
import string
import random

from flask import Blueprint, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from database import db
from models.user import User
from config import get_config

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)
cfg = get_config()


def is_valid_google_client_id(client_id: str) -> bool:
    """Return True when a real Google OAuth web client ID is configured."""
    return bool(
        client_id
        and client_id.endswith(".apps.googleusercontent.com")
        and "PLACEHOLDER" not in client_id.upper()
        and "YOUR_CLIENT_ID" not in client_id.upper()
    )


def generate_token(user_id: int, username: str, role: str) -> str:
    """Generate a JWT access token."""
    import time
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + int(cfg.JWT_ACCESS_TOKEN_EXPIRES.total_seconds()),
    }
    return jwt.encode(payload, cfg.JWT_SECRET_KEY, algorithm="HS256")


def generate_unique_username(base_name: str, max_attempts: int = 100) -> str:
    """
    Generate a unique username from a base name.
    If taken, appends random suffix.
    """
    base_name = base_name.lower().replace(" ", "").replace(".", "")[:20]
    
    # Try base name first
    if not User.query.filter_by(username=base_name).first():
        return base_name
    
    # Try with random suffix
    for _ in range(max_attempts):
        suffix = "".join(random.choices(string.digits, k=4))
        candidate = f"{base_name}{suffix}"
        if not User.query.filter_by(username=candidate).first():
            return candidate
    
    raise ValueError("Could not generate unique username")


# ── POST /register ─────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user.
    Body: { username, email, password }
    """
    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()

    # ── Validation ─────────────────────────────────────────────────────────────
    if not username or not email or not password:
        return jsonify({"error": "username, email, and password are required"}), 400

    if len(username) < 3 or len(username) > 30:
        return jsonify({"error": "Username must be 3–30 characters"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if "@" not in email:
        return jsonify({"error": "Invalid email address"}), 400

    # ── Uniqueness check ───────────────────────────────────────────────────────
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken"}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    # ── Create user ────────────────────────────────────────────────────────────
    user = User(username=username, email=email)
    user.set_password(password)

    # First user becomes admin
    if User.query.count() == 0:
        user.role = "admin"

    db.session.add(user)
    db.session.commit()

    token = generate_token(user.id, user.username, user.role)

    logger.info(f"[Auth] New user registered: {username} ({email})")
    return jsonify({
        "message": "Account created successfully",
        "token": token,
        "user": user.to_dict(),
    }), 201


# ── POST /login ────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login with username/email and password.
    Body: { username_or_email, password }
    """
    data = request.get_json(silent=True) or {}

    identifier = str(data.get("username_or_email", "")).strip()
    password = str(data.get("password", "")).strip()

    if not identifier or not password:
        return jsonify({"error": "Credentials required"}), 400

    # Find by username or email
    user = (
        User.query.filter_by(username=identifier).first()
        or User.query.filter(User.email == identifier.lower()).first()
    )

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.is_active:
        return jsonify({"error": "Account is disabled"}), 403

    # Update last login
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()

    token = generate_token(user.id, user.username, user.role)

    logger.info(f"[Auth] User logged in: {user.username}")
    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": user.to_dict(),
    }), 200


# ── POST /auth/google/token ───────────────────────────────────────────────────
# Google OAuth 2.0 Sign In / Sign Up
# Verifies Google ID token and creates/finds user account

@auth_bp.route("/auth/google/token", methods=["POST"])
def google_auth():
    """
    Authenticate with Google ID token.
    
    This endpoint:
    1. Receives a Google ID token from the frontend
    2. Verifies the token signature against Google's public keys
    3. Extracts user info (sub, email, name, picture)
    4. Creates a new user if google_id doesn't exist
    5. Logs in existing user if google_id is found
    6. Prevents duplicate accounts by unique google_id constraint
    
    Body: { idToken: "eyJhbGc..." }
    Returns: { token: JWT, user: {...}, message: "..." }
    """
    data = request.get_json(silent=True) or {}
    id_token_str = str(data.get("idToken", "")).strip()
    logger.info("[Auth] Google token endpoint called")

    if not id_token_str:
        return jsonify({"error": "idToken is required"}), 400

    if not is_valid_google_client_id(cfg.GOOGLE_CLIENT_ID):
        logger.error("[Auth] GOOGLE_CLIENT_ID not configured")
        return jsonify({"error": "Google authentication not configured on server"}), 500

    try:
        # ── Verify Google ID token ─────────────────────────────────────────────
        # This validates the token signature, expiration, audience, etc.
        payload = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            cfg.GOOGLE_CLIENT_ID
        )
        
        # ── Extract user info from verified token ──────────────────────────────
        google_id = payload.get("sub")  # Unique Google user ID
        email = payload.get("email", "").lower()
        name = payload.get("name", "")
        picture = payload.get("picture", "")

        if not google_id or not email:
            return jsonify({"error": "Invalid Google token: missing required fields"}), 400

        # ── Look up or create user ─────────────────────────────────────────────
        user = User.query.filter_by(google_id=google_id).first()
        
        if user:
            # ── Existing user: update picture, log in ─────────────────────────
            user.profile_picture = picture
            user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.commit()
            
            token = generate_token(user.id, user.username, user.role)
            logger.info(f"[Auth] Google login: {user.username} ({email})")
            
            return jsonify({
                "message": "Google login successful",
                "token": token,
                "user": user.to_dict(),
            }), 200
        
        else:
            # ── New user: create account ───────────────────────────────────────
            # Check if email already registered with different auth provider
            existing_email_user = User.query.filter_by(email=email).first()
            
            if existing_email_user:
                # Email exists but google_id doesn't → link OAuth to existing account
                existing_email_user.google_id = google_id
                existing_email_user.auth_provider = "email_and_google"  # Was email, now linked
                existing_email_user.profile_picture = picture
                existing_email_user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
                db.session.commit()
                
                token = generate_token(existing_email_user.id, existing_email_user.username, existing_email_user.role)
                logger.info(f"[Auth] Email account linked with Google: {existing_email_user.username}")
                
                return jsonify({
                    "message": "Account linked with Google",
                    "token": token,
                    "user": existing_email_user.to_dict(),
                }), 200
            
            else:
                # Brand new user → create account
                username = generate_unique_username(name or email.split("@")[0])
                
                new_user = User(
                    username=username,
                    email=email,
                    google_id=google_id,
                    auth_provider="google",
                    profile_picture=picture,
                )
                # Password not required for OAuth users
                
                # First user becomes admin
                if User.query.count() == 0:
                    new_user.role = "admin"
                
                db.session.add(new_user)
                db.session.commit()
                
                token = generate_token(new_user.id, new_user.username, new_user.role)
                logger.info(f"[Auth] New user registered via Google: {username} ({email})")
                
                return jsonify({
                    "message": "Account created via Google",
                    "token": token,
                    "user": new_user.to_dict(),
                }), 201

    except ValueError as e:
        # Invalid token signature, expired, wrong audience, etc.
        logger.warning(f"[Auth] Google token validation failed: {str(e)}")
        return jsonify({"error": f"Invalid Google token: {str(e)}"}), 401
    
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"[Auth] Google auth error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Google authentication failed: {str(e)}"}), 500


# ── GET /me ────────────────────────────────────────────────────────────────────

@auth_bp.route("/me", methods=["GET"])
def me():
    """Return current user info from JWT token."""
    from routes.utils import token_required
    # Inline token check for this route
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return jsonify({"error": "Token required"}), 401
    try:
        payload = jwt.decode(token, cfg.JWT_SECRET_KEY, algorithms=["HS256"])
        user = db.session.get(User, payload["sub"])
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"user": user.to_dict()}), 200
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
