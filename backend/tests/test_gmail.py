import base64
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import create_app
from config import TestingConfig
from database import db
from models.user import User
from models.gmail_oauth_state import GmailOAuthState
from routes.auth import generate_token
import routes.gmail as gmail


@pytest.fixture
def gmail_client(monkeypatch):
    app = create_app(TestingConfig())
    app.config["TESTING"] = True
    monkeypatch.setattr(gmail.cfg, "GOOGLE_CLIENT_ID", "client.apps.googleusercontent.com")
    monkeypatch.setattr(gmail.cfg, "GOOGLE_CLIENT_SECRET", "test-secret")
    with app.app_context():
        db.drop_all()
        db.create_all()
        user = User(username="mailuser", email="mail@example.test", google_id="google-sub")
        db.session.add(user)
        db.session.commit()
        headers = {"Authorization": "Bearer " + generate_token(user.id, user.username, user.role)}
    yield app.test_client(), headers
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_gmail_endpoints_require_website_auth(gmail_client):
    client, _ = gmail_client
    assert client.get("/api/gmail/messages").status_code == 401


def test_authorization_binds_state_to_linked_google_user(gmail_client):
    client, headers = gmail_client
    response = client.post("/api/gmail/authorize", headers=headers, json={})
    assert response.status_code == 200
    url = response.get_json()["url"]
    assert "gmail.readonly" in url
    assert "gmail.modify" not in url
    with client.application.app_context():
        state = url.split("state=")[1].split("&")[0]
        from urllib.parse import unquote
        record = db.session.get(GmailOAuthState, unquote(state))
        assert record.user_id == 1


def test_unlinked_password_account_cannot_authorize(gmail_client):
    client, _ = gmail_client
    with client.application.app_context():
        unlinked = User(username="passworduser", email="pass@example.test")
        db.session.add(unlinked)
        db.session.commit()
        headers = {"Authorization": "Bearer " + generate_token(unlinked.id, unlinked.username, unlinked.role)}
    assert client.post("/api/gmail/authorize", headers=headers, json={}).status_code == 403


def test_message_listing_paginates_and_returns_all_mail(gmail_client, monkeypatch):
    client, headers = gmail_client
    calls = []
    def fake_get(user, path, params=None):
        calls.append((path, params))
        if path == "messages":
            return {"messages": [{"id": "m1"}], "nextPageToken": "next"}
        return {"id": "m1", "labelIds": ["ARCHIVE"], "snippet": "A snippet", "payload": {"headers": [
            {"name": "From", "value": "Sender <sender@example.test>"}, {"name": "Subject", "value": "Hello"}, {"name": "Date", "value": "Mon, 01 Jan 2024 12:00:00 +0000"}]}}
    monkeypatch.setattr(gmail, "_gmail_get", fake_get)
    result = client.get("/api/gmail/messages?limit=1", headers=headers)
    assert result.status_code == 200
    assert result.get_json()["messages"][0]["subject"] == "Hello"
    assert result.get_json()["nextPageToken"] == "next"
    result = client.get("/api/gmail/messages?pageToken=next", headers=headers)
    assert result.status_code == 200
    assert calls[0][1]["maxResults"] == 1
    assert calls[2][1]["pageToken"] == "next"


def test_detail_sanitizes_html_and_validates_id(gmail_client, monkeypatch):
    client, headers = gmail_client
    encoded = base64.urlsafe_b64encode(b'<script>alert(1)</script><img src="https://remote.test/x"><p>Read me</p>').decode().rstrip("=")
    monkeypatch.setattr(gmail, "_gmail_get", lambda *args, **kwargs: {"id": "safeid", "payload": {
        "headers": [], "mimeType": "text/html", "body": {"data": encoded}}})
    response = client.get("/api/gmail/messages/safeid", headers=headers)
    assert response.status_code == 200
    body = response.get_json()["bodyHtml"]
    assert "<script" not in body and "<img" not in body and "Read me" in body
    assert client.get("/api/gmail/messages/bad%2Fid", headers=headers).status_code == 400


def test_authorization_callback_rejects_google_identity_mismatch(gmail_client, monkeypatch):
    client, _ = gmail_client
    with client.application.app_context():
        db.session.add(GmailOAuthState(state="one-time-state", user_id=1, expires_at=datetime.utcnow() + timedelta(minutes=5)))
        db.session.commit()
    monkeypatch.setattr(gmail.requests, "post", lambda *args, **kwargs: Mock(ok=True, json=lambda: {"access_token": "private", "id_token": "verified-by-google", "expires_in": 3600, "refresh_token": "private-refresh"}))
    monkeypatch.setattr(gmail.google_id_token, "verify_oauth2_token", lambda *args, **kwargs: {"sub": "different-google-account"})
    response = client.post("/api/gmail/oauth/callback", data={"state": "one-time-state", "code": "temporary-code"})
    assert "account_mismatch" in response.location
    with client.application.app_context():
        user = db.session.get(User, 1)
        assert user.gmail_refresh_token is None


def test_authorization_callback_stores_tokens_only_after_identity_match(gmail_client, monkeypatch):
    client, _ = gmail_client
    with client.application.app_context():
        db.session.add(GmailOAuthState(state="matching-state", user_id=1, expires_at=datetime.utcnow() + timedelta(minutes=5)))
        db.session.commit()
    monkeypatch.setattr(gmail.requests, "post", lambda *args, **kwargs: Mock(ok=True, json=lambda: {"access_token": "server-access", "id_token": "verified-by-google", "expires_in": 3600, "refresh_token": "server-refresh"}))
    monkeypatch.setattr(gmail.google_id_token, "verify_oauth2_token", lambda *args, **kwargs: {"sub": "google-sub"})
    response = client.post("/api/gmail/oauth/callback", data={"state": "matching-state", "code": "one-time-code"})
    assert "gmail_connected=1" in response.location
    with client.application.app_context():
        user = db.session.get(User, 1)
        assert user.gmail_access_token == "server-access"
        assert user.gmail_refresh_token == "server-refresh"


def test_frontend_requires_no_email_entry_and_sandboxes_message(gmail_client):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
    page = open(os.path.join(root, "gmail.html"), encoding="utf-8").read()
    script = open(os.path.join(root, "js", "gmail.js"), encoding="utf-8").read()
    assert 'type="email"' not in page
    assert 'sandbox=""' in page
    assert "srcdoc" in script and "img-src 'none'" in script
