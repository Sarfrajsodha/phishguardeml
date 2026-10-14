"""Gmail read-only authorization and mailbox API."""
import base64
import secrets
from html import escape
from html.parser import HTMLParser
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from flask import Blueprint, jsonify, redirect, request, g

from config import get_config
from database import db
from models.gmail_oauth_state import GmailOAuthState
from models.user import User
from routes.utils import token_required

gmail_bp = Blueprint("gmail", __name__)
cfg = get_config()
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailError(Exception):
    def __init__(self, message, status=502):
        self.message, self.status = message, status


class _SafeEmailHTML(HTMLParser):
    """Allow a small formatting subset; omit images, scripts, styles and active content."""
    allowed = {"a", "p", "br", "div", "span", "b", "strong", "i", "em", "u", "ul", "ol", "li", "blockquote", "pre", "code", "table", "thead", "tbody", "tr", "td", "th", "h1", "h2", "h3", "hr"}
    void = {"br", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.suppressed = 0
        self.open_tags = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "iframe", "object", "svg", "form"):
            self.suppressed += 1
            return
        if self.suppressed or tag not in self.allowed:
            return
        safe_attrs = []
        if tag == "a":
            href = dict(attrs).get("href", "").strip()
            if href.lower().startswith(("https://", "http://", "mailto:")):
                safe_attrs.append(f'href="{escape(href, quote=True)}"')
            title = dict(attrs).get("title")
            if title:
                safe_attrs.append(f'title="{escape(title, quote=True)}"')
        if tag in ("td", "th"):
            for name, value in attrs:
                if name in ("colspan", "rowspan") and str(value).isdigit() and 1 <= int(value) <= 20:
                    safe_attrs.append(f'{name}="{escape(str(value), quote=True)}"')
        self.output.append(f"<{tag}{(' ' + ' '.join(safe_attrs)) if safe_attrs else ''}>")
        if tag not in self.void:
            self.open_tags.append(tag)

    def handle_endtag(self, tag):
        if self.suppressed:
            if tag in ("script", "style", "iframe", "object", "svg", "form"):
                self.suppressed -= 1
            return
        if tag in self.open_tags:
            while self.open_tags:
                current = self.open_tags.pop()
                self.output.append(f"</{current}>")
                if current == tag:
                    break

    def handle_data(self, data):
        if not self.suppressed:
            self.output.append(escape(data))

    def result(self):
        while self.open_tags:
            self.output.append(f"</{self.open_tags.pop()}>")
        return "".join(self.output)


def _config_ready():
    return bool(cfg.GOOGLE_CLIENT_ID and cfg.GOOGLE_CLIENT_SECRET)


def _message_error(response):
    if response.status_code in (401, 403):
        return GmailError("Gmail access expired or was revoked. Reauthorize Gmail to continue.", 401)
    if response.status_code == 404:
        return GmailError("This message is no longer available.", 404)
    if response.status_code == 429:
        return GmailError("Gmail is temporarily rate limiting requests. Try again shortly.", 429)
    return GmailError("Gmail could not be reached. Please try again.", 502)


def _valid_token(user):
    access = user.gmail_access_token
    expiry = user.gmail_token_expiry
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if access and expiry and expiry > now + timedelta(seconds=30):
        return access
    refresh = user.gmail_refresh_token
    if not refresh:
        raise GmailError("Gmail access has not been authorized. Grant read-only access to view your mail.", 403)
    try:
        response = requests.post(GOOGLE_TOKEN, data={
            "client_id": cfg.GOOGLE_CLIENT_ID, "client_secret": cfg.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh, "grant_type": "refresh_token",
        }, timeout=15)
    except requests.RequestException:
        raise GmailError("Google authorization service is temporarily unavailable. Try again shortly.", 502)
    if not response.ok:
        user.gmail_refresh_token = user.gmail_access_token = None
        user.gmail_token_expiry = None
        db.session.commit()
        raise GmailError("Gmail access expired or was revoked. Reauthorize Gmail to continue.", 401)
    payload = response.json()
    user.gmail_access_token = payload["access_token"]
    user.gmail_token_expiry = now + timedelta(seconds=int(payload.get("expires_in", 3600)))
    db.session.commit()
    return payload["access_token"]


def _gmail_get(user, path, params=None):
    token = _valid_token(user)
    try:
        response = requests.get(f"{GMAIL_API}/{path}", headers={"Authorization": f"Bearer {token}"}, params=params, timeout=20)
    except requests.RequestException:
        raise GmailError("Gmail could not be reached. Please try again.", 502)
    if not response.ok:
        raise _message_error(response)
    return response.json()


def _headers(payload):
    return {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers", [])}


def _parts(part):
    mime = part.get("mimeType", "")
    body = part.get("body", {}).get("data")
    if body and mime in ("text/plain", "text/html"):
        try:
            decoded = base64.urlsafe_b64decode(body + "==").decode("utf-8", errors="replace")
            yield mime, decoded
        except (ValueError, TypeError):
            pass
    for child in part.get("parts", []):
        yield from _parts(child)


def _summary(data):
    headers = _headers(data.get("payload", {}))
    date = headers.get("date", "")
    try:
        date = parsedate_to_datetime(date).isoformat()
    except (TypeError, ValueError, OverflowError):
        date = ""
    return {"id": data.get("id", ""), "threadId": data.get("threadId", ""),
            "from": headers.get("from", "Unknown sender"), "subject": headers.get("subject", "(No subject)"),
            "date": date, "snippet": data.get("snippet", "")}


@gmail_bp.get("/gmail/status")
@token_required
def status():
    return jsonify({"authorized": bool(g.current_user.gmail_refresh_token), "email": g.current_user.email})


@gmail_bp.post("/gmail/authorize")
@token_required
def authorize():
    if not _config_ready():
        return jsonify({"error": "Gmail authorization is not configured on the server."}), 503
    if not g.current_user.google_id:
        return jsonify({"error": "Gmail is available only when your website account is linked to Google. Sign in with the linked Google account first."}), 403
    state = secrets.token_urlsafe(32)
    db.session.add(GmailOAuthState(state=state, user_id=g.current_user.id,
                                  expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10)))
    db.session.commit()
    from urllib.parse import urlencode
    url = GOOGLE_AUTH + "?" + urlencode({"client_id": cfg.GOOGLE_CLIENT_ID, "redirect_uri": cfg.GOOGLE_REDIRECT_URI,
        "response_type": "code", "response_mode": "form_post", "scope": "openid " + SCOPE, "access_type": "offline", "prompt": "consent",
        "include_granted_scopes": "true", "state": state, "login_hint": g.current_user.email})
    return jsonify({"url": url})


@gmail_bp.post("/gmail/oauth/callback")
def callback():
    state = request.form.get("state", "")
    record = db.session.get(GmailOAuthState, state) if state else None
    if not record or record.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        if record:
            db.session.delete(record); db.session.commit()
        return redirect("/gmail.html?gmail_error=invalid_state")
    user = db.session.get(User, record.user_id)
    db.session.delete(record); db.session.commit()
    if not user or not user.google_id or request.form.get("error") or not request.form.get("code"):
        return redirect("/gmail.html?gmail_error=cancelled")
    if not _config_ready():
        return redirect("/gmail.html?gmail_error=not_configured")
    try:
        token_response = requests.post(GOOGLE_TOKEN, data={"code": request.form["code"], "client_id": cfg.GOOGLE_CLIENT_ID,
            "client_secret": cfg.GOOGLE_CLIENT_SECRET, "redirect_uri": cfg.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"}, timeout=20)
    except requests.RequestException:
        return redirect("/gmail.html?gmail_error=authorization_failed")
    if not token_response.ok:
        return redirect("/gmail.html?gmail_error=authorization_failed")
    tokens = token_response.json()
    access_token = tokens.get("access_token")
    if not access_token:
        return redirect("/gmail.html?gmail_error=authorization_failed")
    try:
        identity = google_id_token.verify_oauth2_token(tokens.get("id_token", ""), google_requests.Request(), cfg.GOOGLE_CLIENT_ID)
    except (ValueError, TypeError):
        identity = {}
    if identity.get("sub") != user.google_id:
        return redirect("/gmail.html?gmail_error=account_mismatch")
    user.gmail_access_token = access_token
    if tokens.get("refresh_token"):
        user.gmail_refresh_token = tokens["refresh_token"]
    user.gmail_token_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=int(tokens.get("expires_in", 3600)))
    db.session.commit()
    return redirect("/gmail.html?gmail_connected=1")


@gmail_bp.get("/gmail/messages")
@token_required
def list_messages():
    try:
        limit = int(request.args.get("limit", "25"))
        if not 1 <= limit <= 50:
            return jsonify({"error": "limit must be between 1 and 50"}), 400
        page_token = request.args.get("pageToken", "")
        if len(page_token) > 2048:
            return jsonify({"error": "Invalid page token"}), 400
        query = {"maxResults": limit}
        if page_token:
            query["pageToken"] = page_token
        result = _gmail_get(g.current_user, "messages", query)
        messages = []
        for item in result.get("messages", []):
            raw = _gmail_get(g.current_user, "messages/" + item["id"], {"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]})
            messages.append(_summary(raw))
        return jsonify({"messages": messages, "nextPageToken": result.get("nextPageToken"), "resultSizeEstimate": result.get("resultSizeEstimate", 0)})
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid pagination parameters"}), 400
    except GmailError as error:
        return jsonify({"error": error.message}), error.status


@gmail_bp.get("/gmail/messages/<path:message_id>")
@token_required
def get_message(message_id):
    if not message_id or len(message_id) > 200 or not all(ch.isalnum() or ch in "-_" for ch in message_id):
        return jsonify({"error": "Invalid message id"}), 400
    try:
        data = _gmail_get(g.current_user, "messages/" + message_id, {"format": "full"})
        parts = list(_parts(data.get("payload", {})))
        plain = next((value for mime, value in parts if mime == "text/plain"), "")
        html = next((value for mime, value in parts if mime == "text/html"), "")
        sanitizer = _SafeEmailHTML()
        if html:
            sanitizer.feed(html)
        safe_html = sanitizer.result() if html else ""
        return jsonify({**_summary(data), "bodyText": plain, "bodyHtml": safe_html})
    except GmailError as error:
        return jsonify({"error": error.message}), error.status
