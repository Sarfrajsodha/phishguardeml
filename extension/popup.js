/**
 * popup.js — Chrome Extension popup logic.
 * Handles auth, email extraction via content script, and result display.
 */

const API = 'http://localhost:5000/api';

// ── Init ───────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  chrome.storage.local.get(['pg_token', 'pg_user'], ({ pg_token, pg_user }) => {
    if (pg_token && pg_user) {
      showMainSection(pg_user);
    }
  });
});

// ── Auth ───────────────────────────────────────────────────────────────────────
async function extLogin() {
  const identifier = document.getElementById('extIdentifier').value.trim();
  const password   = document.getElementById('extPassword').value;
  const btn        = document.getElementById('loginBtn');
  const alertEl    = document.getElementById('authAlert');

  if (!identifier || !password) { showAuthAlert('Fill in all fields.', 'error'); return; }

  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Logging in…';

  try {
    const res = await fetch(`${API}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username_or_email: identifier, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Login failed');

    chrome.storage.local.set({ pg_token: data.token, pg_user: data.user });
    showMainSection(data.user);
  } catch (err) {
    showAuthAlert(err.message, 'error');
    btn.disabled = false;
    btn.innerHTML = '🔐 Login';
  }
}

function extLogout() {
  chrome.storage.local.remove(['pg_token', 'pg_user']);
  document.getElementById('mainSection').style.display = 'none';
  document.getElementById('authSection').style.display = 'block';
  document.getElementById('scanResult').style.display  = 'none';
}

function showMainSection(user) {
  document.getElementById('authSection').style.display = 'none';
  document.getElementById('mainSection').style.display = 'block';
  document.getElementById('loggedUser').textContent = user.username || 'User';
}

// ── Scan Current Email ─────────────────────────────────────────────────────────
async function scanCurrentEmail() {
  const btn = document.getElementById('scanBtn');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Extracting…';
  showScanStatus('Extracting email content from page…', 'info');

  try {
    // Ask content script to extract email data from active tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    let emailData = null;
    try {
      const response = await chrome.tabs.sendMessage(tab.id, { action: 'extractEmail' });
      emailData = response;
    } catch (_) {
      // Content script not injected or no email open
    }

    if (!emailData || !emailData.body) {
      showScanStatus('⚠️ No email detected. Open an email in Gmail or Outlook first.', 'error');
      btn.disabled = false; btn.innerHTML = '🔍 Scan Current Email';
      return;
    }

    showScanStatus('🤖 Running AI analysis…', 'info');
    btn.innerHTML = '<div class="spinner"></div> Analyzing…';

    const { pg_token } = await chrome.storage.local.get('pg_token');

    const res = await fetch(`${API}/scan-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${pg_token}` },
      body: JSON.stringify({ body: emailData.body, subject: emailData.subject || '', sender: emailData.sender || '', source: 'extension' }),
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.error || 'Scan failed');

    showResult(result);
  } catch (err) {
    showScanStatus(`❌ ${err.message}`, 'error');
  } finally {
    btn.disabled = false; btn.innerHTML = '🔍 Scan Current Email';
  }
}

function showResult(result) {
  document.getElementById('scanStatus').style.display = 'none';
  const isPhishing = result.prediction === 'phishing';
  const conf = result.confidence_percent || (result.confidence * 100).toFixed(1);
  const keywords = result.nlp_analysis?.phishing_keywords || [];

  const resultEl = document.getElementById('scanResult');
  resultEl.style.display = 'block';
  resultEl.innerHTML = `
    <div class="result-card ${isPhishing ? 'phishing' : 'safe'}">
      <div class="result-header">
        <span class="result-icon">${isPhishing ? '🚨' : '✅'}</span>
        <div>
          <div class="result-label ${isPhishing ? 'text-red' : 'text-green'}">
            ${isPhishing ? 'PHISHING DETECTED' : 'Email Looks Safe'}
          </div>
          <div style="font-size:11px;color:#7a92b3;">${result.risk_level?.toUpperCase()} RISK</div>
        </div>
      </div>
      <div class="confidence-row">
        <span>AI Confidence</span>
        <span class="conf-value ${isPhishing ? 'text-red' : 'text-green'}">${conf}%</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill ${isPhishing ? 'fill-phishing' : 'fill-safe'}" style="width:${conf}%"></div>
      </div>
      <div class="detail-row"><span>URLs Found</span><span class="detail-val">${result.url_analysis?.total_urls ?? 0}</span></div>
      <div class="detail-row"><span>Suspicious URLs</span><span class="detail-val" style="${result.url_analysis?.suspicious_count > 0 ? 'color:#ff3366' : ''}">${result.url_analysis?.suspicious_count ?? 0}</span></div>
      <div class="detail-row"><span>Model</span><span class="detail-val">${result.model_used}</span></div>
      ${keywords.length ? `<div class="badges">${keywords.slice(0,6).map(k => `<span class="badge badge-kw">${k}</span>`).join('')}</div>` : ''}
    </div>
  `;
}

function showScanStatus(msg, type) {
  const el = document.getElementById('scanStatus');
  el.style.display = 'block';
  el.className = `alert alert-${type}`;
  el.textContent = msg;
  document.getElementById('scanResult').style.display = 'none';
}

function showAuthAlert(msg, type) {
  const el = document.getElementById('authAlert');
  el.className = `alert alert-${type}`;
  el.textContent = msg;
}
