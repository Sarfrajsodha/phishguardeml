# API Documentation — PhishGuard AI

Base URL: `http://localhost:5000/api`

All authenticated endpoints require: `Authorization: Bearer <JWT_TOKEN>`

---

## Authentication

### POST /register
Create a new user account.

**Body:**
```json
{ "username": "alice", "email": "alice@example.com", "password": "securepass123" }
```
**Response 201:**
```json
{ "message": "Account created successfully", "token": "eyJ...", "user": { "id": 1, "username": "alice", "role": "user" } }
```

---

### POST /login
**Body:**
```json
{ "username_or_email": "alice", "password": "securepass123" }
```
**Response 200:**
```json
{ "message": "Login successful", "token": "eyJ...", "user": {...} }
```

---

## Email Scanning

### POST /scan-email ✅ Auth Required

Analyze email content for phishing.

**Body (JSON):**
```json
{
  "subject": "URGENT: Your account suspended",
  "sender": "security@paypal-verify.tk",
  "body": "Click here to verify your PayPal account immediately...",
  "model": "ensemble"
}
```

**OR** multipart file upload with field `file` (.eml).

**Response 200:**
```json
{
  "prediction": "phishing",
  "confidence": 0.9123,
  "confidence_percent": 91.2,
  "risk_level": "critical",
  "model_used": "ensemble",
  "model_breakdown": {
    "logistic_regression": { "prediction": "phishing", "confidence": 0.89 },
    "random_forest":       { "prediction": "phishing", "confidence": 0.94 },
    "naive_bayes":         { "prediction": "phishing", "confidence": 0.91 }
  },
  "nlp_analysis": {
    "token_count": 42,
    "phishing_keywords": ["urgent", "verify", "suspended", "immediately"],
    "urgency_score": 11,
    "caps_ratio": 0.18,
    "exclamation_count": 3,
    "has_html": false
  },
  "url_analysis": {
    "total_urls": 1,
    "suspicious_count": 1,
    "has_http_only": false,
    "has_shortened": false,
    "has_suspicious_tld": true,
    "urls": [{ "url": "http://...", "is_suspicious": true, "flags": ["suspicious_tld"] }]
  },
  "scan_id": 42,
  "scan_timestamp": "2024-05-19T10:30:00"
}
```

---

## History

### GET /history ✅ Auth Required
Returns paginated scan history.

**Query Params:** `page=1`, `per_page=20`, `filter=all|phishing|safe`

### GET /history/:id ✅ Auth Required
Returns scan details.

### DELETE /history/:id ✅ Auth Required
Deletes a scan record.

### GET /history/stats ✅ Auth Required
Returns dashboard statistics.

**Response:**
```json
{
  "total_scans": 150,
  "phishing_count": 43,
  "safe_count": 107,
  "phishing_rate": 28.7,
  "risk_distribution": { "safe": 107, "low": 5, "medium": 18, "high": 12, "critical": 8 }
}
```

---

## Admin (🔐 Admin Role Required)

### GET /admin/stats
### GET /admin/users
### POST /admin/users/:id/toggle
### GET /admin/threats

---

## Model Management

### POST /train-model 🔐 Admin
Triggers background model retraining.
**Response 202:** `{ "message": "Training started", "status": "running" }`

### GET /train-status 🔐 Admin
Check training progress.

### GET /model-metrics
Latest training metrics for all models.

---

## System

### GET /health
```json
{ "status": "ok", "version": "1.0.0", "models_ready": true, "models_loaded": ["logistic_regression", "random_forest", "naive_bayes"] }
```

---

## Error Responses

| Code | Meaning |
|------|---------|
| 400 | Bad request — missing/invalid input |
| 401 | Unauthorized — invalid/expired token |
| 403 | Forbidden — insufficient role |
| 404 | Not found |
| 409 | Conflict — username/email already exists |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
