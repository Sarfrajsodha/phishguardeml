# 🛡️ AI Phishing Email Detector

> **Production-grade AI cybersecurity web application** for detecting phishing emails using Machine Learning, NLP, and heuristic URL analysis.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-black?style=flat-square&logo=flask)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.5-orange?style=flat-square&logo=scikit-learn)
![NLTK](https://img.shields.io/badge/NLTK-3.8-green?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-3-lightblue?style=flat-square&logo=sqlite)

---

## 🏗️ Architecture

```
Frontend (HTML/CSS/JS)
    ↓ REST API (JWT)
Flask Backend (Python)
    ├── Auth Routes      → JWT login/register
    ├── Scanner Route    → NLP + ML + URL analysis
    ├── History Route    → Per-user scan records
    ├── Admin Route      → Platform stats, user mgmt
    └── Model Route      → Train/retrain ML models
         ↓
ML Pipeline (scikit-learn)
    ├── TF-IDF Vectorizer
    ├── Logistic Regression
    ├── Random Forest
    └── Naive Bayes (Ensemble voting)
         ↓
SQLite Database (SQLAlchemy ORM)
    ├── users
    ├── scan_history
    ├── threat_logs
    └── model_metrics

Chrome Extension
    ├── Content Script   → Extracts Gmail/Outlook email
    ├── Popup UI         → Shows risk score
    └── Background SW    → Badge + tab management
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- pip
- (Optional) Docker & Docker Compose

### 1 — Clone & Install

```bash
git clone https://github.com/yourname/phishing-detector.git
cd phishing-detector/backend

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2 — Train ML Models

```bash
# From the backend/ directory
python ml/train.py
```

This generates synthetic phishing/safe email data and trains 3 models:
- Logistic Regression
- Random Forest  
- Naive Bayes

Trained models are saved to `backend/ml/models/`.

### 3 — Start the Backend

```bash
python app.py
# API runs at http://localhost:5000
```

### 4 — Open the Frontend

Open `frontend/index.html` in your browser (or serve with Live Server).

### 5 — Load Chrome Extension

1. Open `chrome://extensions/`
2. Enable **Developer mode**
3. Click **Load unpacked** → select the `extension/` folder
4. Open Gmail → click the PhishGuard shield icon

---

## 🐳 Docker Deployment

```bash
cd phishing-detector
docker-compose up --build
```

The API will be available at `http://localhost:5000`.

---

## ☁️ Cloud Deployment

### Render.com

1. Push to GitHub
2. Create a new **Web Service** on [render.com](https://render.com)
3. Set root directory to `backend/`
4. Build command: `pip install -r requirements.txt && python ml/train.py`
5. Start command: `python app.py`
6. Add environment variables: `SECRET_KEY`, `JWT_SECRET_KEY`, `FLASK_ENV=production`

### Railway.app

```bash
railway login
railway init
railway up
```

Set the same environment variables in the Railway dashboard.

### Frontend (Vercel/Netlify)

The frontend is pure static HTML/CSS/JS — deploy the `frontend/` folder to:
- [Vercel](https://vercel.com): `vercel --prod`
- [Netlify](https://netlify.com): Drag and drop the folder

> ⚠️ Update `API_BASE` in `frontend/js/api.js` to your deployed backend URL.

---

## 📡 API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/register` | ❌ | Create new account |
| POST | `/api/login` | ❌ | Login, get JWT token |
| GET | `/api/me` | ✅ | Current user info |
| POST | `/api/scan-email` | ✅ | Analyze email for phishing |
| GET | `/api/history` | ✅ | Paginated scan history |
| GET | `/api/history/stats` | ✅ | Dashboard statistics |
| POST | `/api/train-model` | 🔐 Admin | Trigger model retraining |
| GET | `/api/model-metrics` | ❌ | Latest model performance |
| GET | `/api/admin/stats` | 🔐 Admin | Platform-wide statistics |
| GET | `/api/admin/users` | 🔐 Admin | List all users |
| GET | `/api/health` | ❌ | Health check |

---

## 🧪 Testing

### Unit Tests

```bash
cd backend
pytest tests/ -v
```

### API Testing (curl)

```bash
# Register
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@test.com","password":"password123"}'

# Login
TOKEN=$(curl -s -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username_or_email":"admin","password":"password123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Scan a phishing email
curl -X POST http://localhost:5000/api/scan-email \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"subject":"URGENT: Account suspended","sender":"security@paypal-verify.tk","body":"Click here immediately to verify your account or it will be deleted!"}'
```

---

## 📁 Project Structure

```
phishing-detector/
├── backend/
│   ├── app.py               # Flask application factory
│   ├── config.py            # Environment configuration
│   ├── database.py          # SQLAlchemy setup
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── scan_history.py
│   │   └── threat_log.py
│   ├── routes/              # Flask blueprints
│   │   ├── auth.py
│   │   ├── scanner.py
│   │   ├── history.py
│   │   ├── admin.py
│   │   ├── model_routes.py
│   │   └── utils.py
│   ├── services/            # Business logic
│   │   ├── nlp_processor.py
│   │   ├── url_scanner.py
│   │   ├── email_parser.py
│   │   └── ml_predictor.py
│   └── ml/
│       ├── train.py         # Model training script
│       └── models/          # Saved .pkl files
├── frontend/
│   ├── index.html           # Login/Register
│   ├── dashboard.html       # Stats & charts
│   ├── scanner.html         # Email scanner
│   ├── history.html         # Scan history
│   ├── admin.html           # Admin panel
│   ├── css/style.css
│   └── js/
│       ├── api.js
│       ├── auth.js
│       ├── scanner.js
│       ├── dashboard.js
│       ├── history.js
│       └── admin.js
├── extension/
│   ├── manifest.json        # Chrome MV3
│   ├── popup.html/js        # Extension UI
│   ├── content.js           # Gmail/Outlook extractor
│   └── background.js        # Service worker
├── dataset/
│   └── preprocess.py
├── notebooks/
│   └── model_training.ipynb
├── docs/
│   ├── API.md
│   ├── ARCHITECTURE.md
│   └── DEPLOYMENT.md
└── docker-compose.yml
```

---

## 🔐 Security Features

- **JWT Authentication** — stateless, expiry-controlled tokens
- **Bcrypt Password Hashing** — via Werkzeug
- **Rate Limiting** — Flask-Limiter (100 req/hour default)
- **CORS Protection** — configurable origins
- **Input Sanitization** — all inputs validated before DB write
- **SQL Injection Prevention** — SQLAlchemy ORM (no raw SQL)
- **Role-based Access Control** — user / admin roles

---

## 🤖 ML Models

| Model | Type | Notes |
|-------|------|-------|
| Logistic Regression | Linear classifier | Fast, interpretable |
| Random Forest | Ensemble trees | High accuracy, robust |
| Naive Bayes | Probabilistic | Great for text classification |
| **Ensemble** | Soft voting | Averages all 3 — default |

**NLP Pipeline:**
1. HTML stripping → URL/email replacement
2. NLTK tokenization
3. Stopword removal
4. WordNet lemmatization
5. TF-IDF vectorization (5000 features, bigrams)

---

## 🔮 Future Improvements

- [ ] BERT/DistilBERT transformer model for higher accuracy
- [ ] Real-time email header analysis (SPF/DKIM/DMARC)
- [ ] VirusTotal API integration for URL reputation checks
- [ ] PDF export of scan reports
- [ ] Email provider OAuth integration
- [ ] Slack/Teams webhook threat alerts
- [ ] Active Learning — retrain on user-confirmed phishing

---

## 📄 License

MIT License — free to use for educational and portfolio projects.

---

*Built for: College Projects · Hackathons · Internship Portfolios · GitHub Showcase*
