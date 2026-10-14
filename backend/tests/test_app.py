"""
Unit tests for PhishGuard AI backend.
Tests NLP processor, URL scanner, and API endpoints.

Run with: pytest tests/ -v
"""

import sys
import os
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.nlp_processor import NLPProcessor
from services.url_scanner import URLScanner


# ── NLP Processor Tests ────────────────────────────────────────────────────────

class TestNLPProcessor:
    def setup_method(self):
        self.nlp = NLPProcessor()

    def test_process_returns_dict(self):
        result = self.nlp.process("Hello world")
        assert isinstance(result, dict)
        assert "processed_text" in result
        assert "phishing_keywords" in result

    def test_detects_urgency_keywords(self):
        text = "URGENT: Verify your account immediately or it will be suspended!"
        result = self.nlp.process(text)
        assert result["urgency_score"] > 0
        assert any(kw in result["phishing_keywords"] for kw in ["urgent", "verify", "suspended", "immediately"])

    def test_safe_email_low_urgency(self):
        text = "Hi team, please find the meeting notes attached. Thanks!"
        result = self.nlp.process(text)
        assert result["urgency_score"] == 0 or result["urgency_score"] < 3

    def test_caps_ratio(self):
        text = "CLICK HERE NOW TO WIN A PRIZE"
        result = self.nlp.process(text)
        assert result["caps_ratio"] > 0.5

    def test_html_detection(self):
        html_text = '<p>Click <a href="http://evil.tk">here</a> to verify</p>'
        result = self.nlp.process(html_text)
        assert result["has_html"] is True

    def test_exclamation_count(self):
        text = "Win a prize! Claim now! Limited offer! Act fast!"
        result = self.nlp.process(text)
        assert result["exclamation_count"] >= 4

    def test_empty_string(self):
        result = self.nlp.process("")
        assert result["processed_text"] == ""
        assert result["keyword_count"] == 0

    def test_get_features_returns_string(self):
        text = "Your account has been suspended. Verify now."
        features = self.nlp.get_features_for_model(text)
        assert isinstance(features, str)
        assert len(features) > 0


# ── URL Scanner Tests ─────────────────────────────────────────────────────────

class TestURLScanner:
    def setup_method(self):
        self.scanner = URLScanner()

    def test_no_urls(self):
        result = self.scanner.analyze_text("No links in this email.")
        assert result["total_urls"] == 0
        assert result["suspicious_count"] == 0

    def test_safe_https_url(self):
        result = self.scanner.analyze_text("Visit https://www.google.com for more info.")
        assert result["total_urls"] == 1
        safe_urls = [u for u in result["urls"] if not u["is_suspicious"]]
        assert len(safe_urls) >= 1

    def test_suspicious_tld(self):
        result = self.scanner.analyze_text("Click http://verify-account.tk/login now!")
        assert result["suspicious_count"] >= 1
        assert result["has_suspicious_tld"] is True

    def test_url_shortener_flagged(self):
        result = self.scanner.analyze_text("Click bit.ly/scam123 to claim your prize.")
        flagged = [u for u in result["urls"] if u["is_shortened"]]
        assert len(flagged) >= 1

    def test_http_only_flagged(self):
        result = self.scanner.analyze_text("Login at http://example.com/login")
        assert result["has_http_only"] is True

    def test_multiple_urls(self):
        text = "See https://safe.com and also http://evil.xyz/hack and bit.ly/x"
        result = self.scanner.analyze_text(text)
        assert result["total_urls"] >= 2

    def test_ip_as_domain(self):
        result = self.scanner.analyze_text("Go to http://192.168.1.1/phish now")
        suspicious = [u for u in result["urls"] if "ip_address_as_domain" in u.get("flags", [])]
        assert len(suspicious) >= 1


# ── Flask API Tests ───────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Create Flask test app with in-memory SQLite."""
    os.environ["FLASK_ENV"] = "testing"
    from app import create_app
    from config import TestingConfig
    flask_app = create_app(TestingConfig())
    return flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_headers(client):
    """Register and login, return auth headers."""
    client.post("/api/register", json={
        "username": "testuser", "email": "test@test.com", "password": "password123"
    })
    resp = client.post("/api/login", json={
        "username_or_email": "testuser", "password": "password123"
    })
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}

class TestAPI:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_register_success(self, client):
        resp = client.post("/api/register", json={
            "username": "newuser", "email": "new@test.com", "password": "password123"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "token" in data

    def test_register_duplicate(self, client):
        client.post("/api/register", json={"username": "dup", "email": "dup@test.com", "password": "pass1234"})
        resp = client.post("/api/register", json={"username": "dup", "email": "dup@test.com", "password": "pass1234"})
        assert resp.status_code == 409

    def test_login_invalid(self, client):
        resp = client.post("/api/login", json={"username_or_email": "nobody", "password": "wrong"})
        assert resp.status_code == 401

    def test_scan_requires_auth(self, client):
        resp = client.post("/api/scan-email", json={"body": "test"})
        assert resp.status_code == 401

    def test_scan_email(self, client, auth_headers):
        resp = client.post("/api/scan-email", json={
            "body": "URGENT! Click http://evil.tk to verify your account now!",
            "subject": "Account suspended",
            "sender": "noreply@evil.tk",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "prediction" in data
        assert "confidence" in data
        assert data["prediction"] in ["phishing", "safe", "unknown"]

    def test_history_requires_auth(self, client):
        resp = client.get("/api/history")
        assert resp.status_code == 401

    def test_history_empty(self, client, auth_headers):
        resp = client.get("/api/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "scans" in data
