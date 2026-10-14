/**
 * api.js — Centralized API client for PhishGuard AI frontend.
 * Handles authentication headers, base URL, and JSON responses.
 */

const API_BASE = `${window.location.origin}/api`;

/**
 * Make an authenticated API request.
 * @param {string} endpoint
 * @param {object} options — fetch options
 */
async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem('phishguard_token');
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const isAuthAttempt = ['/login', '/register', '/auth/google/token'].includes(endpoint);
    const gmailAuthorizationError = endpoint.startsWith('/gmail/') && /Gmail access|Gmail authorization/i.test(data.error || '');
    if (response.status === 401 && !isAuthAttempt && !gmailAuthorizationError) {
      // Token expired on a protected route.
      localStorage.removeItem('phishguard_token');
      localStorage.removeItem('phishguard_user');
      window.location.href = 'index.html';
    }
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

/** POST request with JSON body */
async function apiPost(endpoint, body) {
  return apiRequest(endpoint, { method: 'POST', body: JSON.stringify(body) });
}

/** GET request */
async function apiGet(endpoint) {
  return apiRequest(endpoint, { method: 'GET' });
}

/** Multipart form POST for file uploads */
async function apiUpload(endpoint, formData) {
  const token = localStorage.getItem('phishguard_token');
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}${endpoint}`, { method: 'POST', headers, body: formData });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

/** Format a UTC ISO string to local readable date */
function formatDate(isoString) {
  if (!isoString) return '—';
  return new Date(isoString).toLocaleString();
}

/** Format confidence as percent string */
function formatConfidence(score) {
  return `${(score * 100).toFixed(1)}%`;
}

/** Get badge HTML for prediction */
function predictionBadge(prediction) {
  if (prediction === 'phishing') return `<span class="badge badge-phishing">Phishing</span>`;
  if (prediction === 'safe')     return `<span class="badge badge-safe">Safe</span>`;
  return `<span class="badge badge-low">Unknown</span>`;
}

/** Get badge HTML for risk level */
function riskBadge(level) {
  const map = {
    critical: `<span class="badge badge-critical">Critical</span>`,
    high:     `<span class="badge badge-high">High</span>`,
    medium:   `<span class="badge badge-medium">Medium</span>`,
    low:      `<span class="badge badge-low">Low</span>`,
    safe:     `<span class="badge badge-safe">Safe</span>`,
  };
  return map[level] || `<span class="badge badge-low">${level}</span>`;
}

/** Escape text before injecting into UI markup */
function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/** Toast notifications used by visual flows */
function showToast(title, messageOrType = '', maybeType = '') {
  const knownTypes = ['success', 'error', 'info', 'warning'];
  let message = messageOrType;
  let type = maybeType || 'info';

  if (knownTypes.includes(messageOrType) && !maybeType) {
    type = messageOrType;
    message = '';
  }
  if (!knownTypes.includes(type)) type = 'info';

  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  Object.assign(container.style, {
    position: 'fixed',
    bottom: '18px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: '9999',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '10px',
    pointerEvents: 'none',
    maxWidth: '360px',
    width: 'auto',
  });

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  Object.assign(toast.style, {
    minWidth: '260px',
    maxWidth: '360px',
    borderRadius: '16px',
    padding: '14px 16px',
    background: 'rgba(255,255,255,0.98)',
    border: '1px solid rgba(15,23,42,0.08)',
    boxShadow: '0 16px 45px rgba(15,23,42,0.12)',
    color: '#111827',
    fontSize: '14px',
    lineHeight: '1.5',
    backdropFilter: 'blur(14px)',
    opacity: '1',
    transform: 'translateY(0)',
    transition: 'transform .22s ease, opacity .22s ease',
    pointerEvents: 'auto',
    overflowWrap: 'anywhere',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  });

  if (type === 'success') toast.style.borderColor = 'rgba(14,168,130,0.18)';
  if (type === 'error') toast.style.borderColor = 'rgba(232,75,106,0.18)';
  if (type === 'warning') toast.style.borderColor = 'rgba(245,158,11,0.18)';
  if (type === 'info') toast.style.borderColor = 'rgba(59,130,246,0.18)';

  toast.innerHTML = `
    <div class="toast-title">${escapeHtml(title)}</div>
    ${message ? `<div class="toast-message">${escapeHtml(message)}</div>` : ''}
  `;
  container.appendChild(toast);

  window.setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    window.setTimeout(() => toast.remove(), 220);
  }, 4000);
}

function initChromeUi() {
  const currentPage = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-link[href]').forEach(link => {
    const target = link.getAttribute('href');
    link.classList.toggle('active', target === currentPage);
  });

  const userJson = localStorage.getItem('phishguard_user');
  if (!userJson) return;
  try {
    const user = JSON.parse(userJson);
    const username = user.username || 'User';
    const initial = username.charAt(0).toUpperCase();
    ['topUsername', 'navUsername'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = username;
    });
    ['topAvatar', 'navAvatar'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = initial;
    });
    document.querySelectorAll('[data-user-name]').forEach(el => { el.textContent = username; });
    document.querySelectorAll('[data-user-avatar]').forEach(el => { el.textContent = initial; });
  } catch (_) {}
}

document.addEventListener('DOMContentLoaded', initChromeUi);
