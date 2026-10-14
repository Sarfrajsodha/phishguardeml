# Google OAuth 2.0 Integration Setup Guide

## Gmail mailbox page (read-only authorization)

The existing Google Identity Services sign-in remains unchanged. Gmail access uses a separate server-side OAuth authorization-code flow and is offered only when the signed-in website user has a linked Google subject (`google_id`). The callback verifies that subject before saving any Gmail tokens. Access and refresh tokens are stored in the server database only; protect the database with the deployment's disk/database encryption and access controls. Never put tokens or `GOOGLE_CLIENT_SECRET` in frontend configuration.

Additional backend environment values:

```env
GOOGLE_CLIENT_ID=your-web-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-web-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5000/api/gmail/oauth/callback
```

In Google Cloud Console, enable the Gmail API and configure the OAuth consent screen. The app requests the Gmail `https://www.googleapis.com/auth/gmail.readonly` scope plus the OpenID identity scope needed to verify the same Google subject linked at sign-in; it does not request Gmail write access or a separate email permission. Add the exact callback URL above to the same Web application OAuth client under **Authorized redirect URIs** (use the deployed HTTPS API origin outside local development). Publish or add test users as required by the consent-screen audience. Message bodies are retrieved only after the user opens a message. Users who signed in by password without a linked Google account must sign in with the linked Google identity; the Gmail page does not allow choosing another mailbox.

Existing SQLite databases are upgraded on startup with nullable token columns. Tokens remain server-side. Revoked or expired grants can be renewed from the Gmail page.

## Overview

This guide explains how to set up Google Sign-In / Sign-Up functionality for PhishGuard. The integration allows users to authenticate using their Google accounts without creating a separate password.

---

## Architecture & Security

### Backend Flow
```
Frontend (Google ID Token)
    ↓
Backend Route: POST /auth/google/token
    ↓
[1] Verify token signature against Google's public keys
[2] Extract: google_id, email, name, picture
[3] Look up by google_id (unique constraint)
    ├─ IF found: Update last_login, return JWT
    └─ IF not found: 
        ├─ IF email exists (legacy user): Link OAuth, return JWT
        └─ IF new email: Create account with google_id, return JWT
    ↓
Generate JWT token (same format as email/password login)
    ↓
Frontend stores JWT in localStorage → redirect to dashboard
```

### Security Practices Implemented
- ✅ **Server-side token verification**: We verify the Google ID token on the backend using `google.auth.transport.requests` and `google.oauth2.id_token`
- ✅ **Unique google_id constraint**: Prevents duplicate Google accounts
- ✅ **Password not required**: Users authenticating via Google don't need a password
- ✅ **Same JWT session**: Google users receive the same JWT token format as email/password users
- ✅ **Account linking**: If a Google email matches an existing email/password account, they're seamlessly linked
- ✅ **No cross-site requests**: Token verification happens server-side only

---

## Step 1: Google Cloud Console Setup

### 1.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top
3. Click **NEW PROJECT**
4. Enter project name: `PhishGuard` (or your preferred name)
5. Click **CREATE** and wait for the project to be created

### 1.2 Enable Google Identity Services API

1. In the Google Cloud Console, go to **APIs & Services** → **Library**
2. Search for `Google+ API` (or `Identity Toolkit`)
3. Click **Google+ API** and click **ENABLE**
4. (Alternative: The ID token verification works with just the OAuth 2.0 credentials, no additional API needed)

### 1.3 Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ CREATE CREDENTIALS** at the top
3. Select **OAuth 2.0 Client ID**
4. Choose application type: **Web application**
5. Name it: `PhishGuard Web Client`

### 1.4 Configure Authorized Redirect URIs

Under **Authorized redirect URIs**, add:
```
http://localhost:3000
http://localhost:5000
http://127.0.0.1:3000
http://127.0.0.1:5000
https://yourdomain.com      # Add your production domain here
```

Click **CREATE**

### 1.5 Copy Your Client ID

A dialog will appear with your credentials:
- **Client ID**: `YOUR_CLIENT_ID.apps.googleusercontent.com` ← **COPY THIS**
- **Client Secret**: For server-to-server API calls (not needed for frontend)

Save these credentials securely.

---

## Step 2: Backend Installation

### 2.1 Install Google Auth Library

```bash
cd backend

# Install the Google authentication library
pip install google-auth==2.28.1 google-auth-httplib2==0.2.0

# Or if using requirements.txt (already done):
pip install -r requirements.txt
```

### 2.2 Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Google OAuth 2.0 Configuration
GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com

# Other existing configurations
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here
```

### 2.3 Update config.py

The config.py has already been updated to include:
```python
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
```

This reads the `GOOGLE_CLIENT_ID` from your `.env` file.

### 2.4 Database Migration (if needed)

If you're upgrading an existing PhishGuard installation, the User model has been updated with three new columns:

```sql
ALTER TABLE users ADD COLUMN google_id VARCHAR(255) UNIQUE NULL;
ALTER TABLE users ADD COLUMN auth_provider VARCHAR(20) NULL;
ALTER TABLE users ADD COLUMN profile_picture VARCHAR(500) NULL;
ALTER TABLE users MODIFY password_hash VARCHAR(255) NULL;
```

**When using SQLAlchemy (automatic)**:
- Delete `backend/phishing_detector.db` to regenerate with new schema
- Or the database will auto-migrate on first run

---

## Step 3: Frontend Configuration

### 3.1 Set Google Client ID

In `frontend/index.html`, the Google Client ID is set automatically:

```javascript
window.GOOGLE_CLIENT_ID = localStorage.getItem('google_client_id') || 
                          (typeof GOOGLE_CLIENT_ID !== 'undefined' ? GOOGLE_CLIENT_ID : '');
```

**Option 1: Set in localStorage (from backend API)**
```javascript
// After login/startup, fetch and store it
fetch('http://localhost:5000/api/config')
  .then(r => r.json())
  .then(data => {
    localStorage.setItem('google_client_id', data.google_client_id);
  });
```

**Option 2: Set directly in index.html (for development)**
```html
<script>
  window.GOOGLE_CLIENT_ID = 'YOUR_CLIENT_ID.apps.googleusercontent.com';
</script>
```

**Option 3: Create a config endpoint (recommended for production)**

In `backend/routes/auth.py`, add:
```python
@auth_bp.route("/config", methods=["GET"])
def get_config():
    return jsonify({
        "google_client_id": cfg.GOOGLE_CLIENT_ID,
    }), 200
```

Then in frontend, load it on page load:
```javascript
(function loadConfig() {
  fetch('/api/config')
    .then(r => r.json())
    .then(data => {
      window.GOOGLE_CLIENT_ID = data.google_client_id;
    })
    .catch(e => console.warn('Config load failed:', e));
})();
```

---

## Step 4: Run the Application

### 4.1 Start Backend

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Backend runs on `http://localhost:5000`

### 4.2 Open Frontend

```bash
# In another terminal
cd frontend
# Open in browser or use Live Server
open index.html
# Or with Python:
python -m http.server 3000
```

Frontend runs on `http://localhost:3000`

---

## Step 5: Test Google Sign-In

### 5.1 Login Page

1. Go to `http://localhost:3000/index.html`
2. Click **"Continue with Google"** button
3. A Google sign-in popup will appear
4. Sign in with your Google account
5. You should be redirected to the dashboard

### 5.2 Register Page

1. Click the **"Register"** tab
2. Click **"Continue with Google"** button
3. If you're using a new Google account (different email), a new PhishGuard account will be created
4. If you use the same Google account, you'll be logged into the existing account

### 5.3 Account Linking

If you:
1. Registered with email/password as `user@example.com`
2. Later sign in with Google using the same `user@example.com`
3. The accounts will automatically be linked

---

## Database Schema

### Updated User Model

```python
class User(db.Model):
    # ── Existing fields ───────────────────
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)  # Now nullable for OAuth
    role = db.Column(db.String(20), default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # ── NEW OAuth fields ──────────────────
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    auth_provider = db.Column(db.String(20), nullable=True)  # 'google', 'email', etc.
    profile_picture = db.Column(db.String(500), nullable=True)  # Avatar URL
```

### User to_dict() Output

```json
{
  "id": 1,
  "username": "john.doe",
  "email": "john.doe@gmail.com",
  "role": "user",
  "created_at": "2024-05-24T10:30:00",
  "last_login": "2024-05-24T15:45:30",
  "is_active": true,
  "auth_provider": "google",
  "profile_picture": "https://lh3.googleusercontent.com/..."
}
```

---

## API Endpoints

### New Google OAuth Endpoint

**POST** `/api/auth/google/token`

Verify Google ID token and authenticate user.

**Request:**
```json
{
  "idToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjEifQ.eyJzdWIiOiIxMDc..."
}
```

**Response (New User):**
```json
{
  "message": "Account created via Google",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "username": "john.doe1234",
    "email": "john.doe@gmail.com",
    "role": "user",
    "auth_provider": "google",
    "profile_picture": "https://lh3.googleusercontent.com/..."
  }
}
```

**Response (Existing User):**
```json
{
  "message": "Google login successful",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": { ... }
}
```

**Error (Invalid Token):**
```json
{
  "error": "Invalid Google token: Token expired"
}
```

---

## Production Deployment

### Environment Variables (Production)

Add these to your production `.env`:
```bash
FLASK_ENV=production
GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com
SECRET_KEY=generate-a-strong-random-key
JWT_SECRET_KEY=generate-another-strong-random-key
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Authorized Domains

In Google Cloud Console, add your production domain to **Authorized redirect URIs**:
```
https://yourdomain.com
https://www.yourdomain.com
```

### Security Considerations

1. **Never commit `.env` files** to version control
2. **Use HTTPS only** in production
3. **Rotate secrets regularly**
4. **Use environment-specific Client IDs** (dev, staging, prod)
5. **Monitor OAuth token usage** via Google Cloud Console

---

## Troubleshooting

### "GOOGLE_CLIENT_ID not configured"

**Error**: Shows in console or when clicking Google button

**Fix**:
1. Ensure `GOOGLE_CLIENT_ID` is set in `backend/.env`
2. Restart the backend server
3. Refresh the frontend page
4. Check that `window.GOOGLE_CLIENT_ID` is set in browser console:
   ```javascript
   console.log(window.GOOGLE_CLIENT_ID);
   ```

### "Invalid Google token"

**Error**: Backend rejects the token

**Possible Causes**:
1. Token is expired (>1 hour old)
2. Client ID mismatch (frontend uses different client ID than backend)
3. Network issue during verification

**Fix**:
1. Verify frontend Client ID matches backend config
2. Check Google Cloud Console for API errors
3. Ensure internet connection

### "Email already registered"

**Error**: When linking OAuth to existing account

**This is expected**: If you previously registered with email/password, signing in with Google using the same email will link the accounts.

### Google popup not appearing

**Possible Causes**:
1. JavaScript not loading
2. Popup blocker enabled
3. Third-party cookies disabled

**Fix**:
1. Check browser console for errors
2. Disable popup blocker for localhost
3. Enable third-party cookies in browser settings

---

## Existing Features Preserved

✅ Email/password login still works
✅ Email/password registration still works  
✅ JWT session management unchanged
✅ All existing routes protected
✅ Admin panel functionality preserved
✅ History and scan functionality untouched
✅ Database backward compatible (new columns nullable)

---

## Files Modified

### Backend
- ✏️ `backend/models/user.py` - Added OAuth fields
- ✏️ `backend/routes/auth.py` - Added `/auth/google/token` endpoint
- ✏️ `backend/config.py` - Added GOOGLE_CLIENT_ID configuration
- ✏️ `backend/requirements.txt` - Added google-auth dependencies

### Frontend
- ✏️ `frontend/index.html` - Added Google script and buttons
- ✏️ `frontend/js/auth.js` - Added Google Sign-In handler

---

## References

- [Google Identity Services Documentation](https://developers.google.com/identity/gsi/web)
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [google-auth-httplib2 Library](https://github.com/googleapis/google-auth-library-python-httplib2)
- [JWT Concepts](https://jwt.io)

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the implementation comments in code
3. Check Google Cloud Console activity logs
4. Enable verbose logging in `config.py` (`LOG_LEVEL=DEBUG`)

