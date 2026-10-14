/**
 * auth.js - Authentication logic for login, register, Google Sign-In,
 * and session management.
 */

(function guardRoute() {
  const publicPages = ['index.html', '/', ''];
  const path = window.location.pathname.split('/').pop() || 'index.html';
  const isPublic = publicPages.includes(path);
  const token = localStorage.getItem('phishguard_token');

  if (!isPublic && !token) {
    window.location.href = 'index.html';
    return;
  }
  if (isPublic && token) {
    window.location.href = 'dashboard.html';
  }
})();

(function populateNav() {
  const userJson = localStorage.getItem('phishguard_user');
  if (!userJson) return;
  try {
    const user = JSON.parse(userJson);
    const navUsername = document.getElementById('navUsername');
    const navAvatar = document.getElementById('navAvatar');
    const adminLink = document.getElementById('adminNavLink');
    if (navUsername) navUsername.textContent = user.username || 'User';
    if (navAvatar) navAvatar.textContent = (user.username || 'U')[0].toUpperCase();
    if (adminLink && user.role !== 'admin') adminLink.style.display = 'none';
  } catch (_) {}
})();

function logout() {
  localStorage.removeItem('phishguard_token');
  localStorage.removeItem('phishguard_user');
  localStorage.removeItem('role');
  window.location.href = 'index.html';
}

function switchTab(tab) {
  document.getElementById('loginForm').classList.toggle('hidden', tab !== 'login');
  document.getElementById('registerForm').classList.toggle('hidden', tab !== 'register');
  document.getElementById('loginTab').classList.toggle('active', tab === 'login');
  document.getElementById('registerTab').classList.toggle('active', tab === 'register');
  clearAlert();
}

function showAlert(msg, type = 'error') {
  const el = document.getElementById('authAlert');
  if (!el) return;
  el.className = `auth-alert show ${type}`;
  el.textContent = msg;
}

function clearAlert() {
  const el = document.getElementById('authAlert');
  if (!el) return;
  el.className = 'auth-alert';
  el.textContent = '';
}

async function handleLogin(e) {
  e.preventDefault();
  clearAlert();

  const btn = document.getElementById('loginBtn');
  const identifier = document.getElementById('loginIdentifier').value.trim();
  const password = document.getElementById('loginPassword').value;

  if (!identifier || !password) {
    showAlert('Please fill in all fields.');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;"></span><span>Logging in...</span>';

  try {
    const data = await apiPost('/login', { username_or_email: identifier, password });
    localStorage.setItem('phishguard_token', data.token);
    localStorage.setItem('phishguard_user', JSON.stringify(data.user));
    localStorage.setItem('role', data.user?.role || '');
    window.location.href = 'dashboard.html';
  } catch (err) {
    showAlert(err.message || 'Login failed. Check credentials.');
    btn.disabled = false;
    btn.innerHTML = '<svg class="icon" viewBox="0 0 24 24"><path d="M10 17l5-5-5-5"/><path d="M15 12H3"/><path d="M21 4v16"/></svg><span>Login to Dashboard</span>';
  }
}

async function handleRegister(e) {
  e.preventDefault();
  clearAlert();

  const btn = document.getElementById('registerBtn');
  const username = document.getElementById('regUsername').value.trim();
  const email = document.getElementById('regEmail').value.trim();
  const password = document.getElementById('regPassword').value;

  if (!username || !email || !password) {
    showAlert('All fields required.');
    return;
  }
  if (password.length < 8) {
    showAlert('Password must be at least 8 characters.');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;"></span><span>Creating account...</span>';

  try {
    const data = await apiPost('/register', { username, email, password });
    localStorage.setItem('phishguard_token', data.token);
    localStorage.setItem('phishguard_user', JSON.stringify(data.user));
    localStorage.setItem('role', data.user?.role || '');
    window.location.href = 'dashboard.html';
  } catch (err) {
    showAlert(err.message || 'Registration failed.');
    btn.disabled = false;
    btn.innerHTML = '<svg class="icon" viewBox="0 0 24 24"><path d="M12 5v14"/><path d="M5 12h14"/></svg><span>Create Account</span>';
  }
}

function isValidGoogleClientId(clientId) {
  return Boolean(
    clientId &&
    clientId.endsWith('.apps.googleusercontent.com') &&
    !clientId.toUpperCase().includes('PLACEHOLDER') &&
    !clientId.toUpperCase().includes('YOUR_CLIENT_ID')
  );
}

async function loadGoogleClientId() {
  try {
    const config = await apiGet('/config/public');
    if (isValidGoogleClientId(config.google_client_id)) {
      localStorage.setItem('google_client_id', config.google_client_id);
      return config.google_client_id;
    }
  } catch (err) {
    console.warn('[Auth] Could not load public auth config:', err);
  }

  const fallbackClientId = window.GOOGLE_CLIENT_ID || localStorage.getItem('google_client_id') || '';
  return isValidGoogleClientId(fallbackClientId) ? fallbackClientId : '';
}

function renderGoogleUnavailable() {
  ['loginGoogleBtn', 'registerGoogleBtn'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = '<button type="button" class="btn-oauth" disabled><span>Google not configured</span></button>';
  });
}

function renderGoogleButtons() {
  ['loginGoogleBtn', 'registerGoogleBtn'].forEach(id => {
    const el = document.getElementById(id);
    if (!el || el.dataset.rendered === 'true') return;
    el.innerHTML = '';
    window.google.accounts.id.renderButton(el, {
      theme: 'outline',
      size: 'large',
      text: 'continue_with',
      shape: 'rectangular',
      logo_alignment: 'left',
      width: Math.max(260, Math.floor(el.getBoundingClientRect().width || 364)),
    });
    el.dataset.rendered = 'true';
  });
}

function handleGoogleSignIn() {
  showAlert('Google Sign-In is still loading. Please try again in a moment.', 'error');
}

async function handleGoogleResponse(response) {
  try {
    showAlert('Google account selected. Creating your session...', 'success');
    console.info('[Auth] Google credential callback received');

    if (!response || !response.credential) {
      throw new Error('No credential received from Google');
    }

    const data = await apiPost('/auth/google/token', { idToken: response.credential });
    localStorage.setItem('phishguard_token', data.token);
    localStorage.setItem('phishguard_user', JSON.stringify(data.user));
    localStorage.setItem('role', data.user?.role || '');

    showAlert('Signed in successfully!', 'success');
    setTimeout(() => {
      window.location.href = 'dashboard.html';
    }, 800);
  } catch (err) {
    console.error('[Auth] Google response handling error:', err);
    showAlert('Error: ' + (err.message || 'Authentication failed'), 'error');
  }
}

async function initGoogleSignIn() {
  const hasGoogleButton = document.getElementById('loginGoogleBtn') || document.getElementById('registerGoogleBtn');
  if (!hasGoogleButton) return;

  const clientId = await loadGoogleClientId();
  if (!clientId) {
    renderGoogleUnavailable();
    return;
  }

  window.GOOGLE_CLIENT_ID = clientId;

  for (let attempts = 0; attempts < 20; attempts += 1) {
    if (window.google && window.google.accounts && window.google.accounts.id) break;
    await new Promise(resolve => setTimeout(resolve, 250));
  }

  if (!window.google || !window.google.accounts || !window.google.accounts.id) {
    renderGoogleUnavailable();
    return;
  }

  try {
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: handleGoogleResponse,
    });
    window.googleInitialized = true;
    renderGoogleButtons();
  } catch (err) {
    console.error('[Auth] Failed to initialize Google:', err);
    renderGoogleUnavailable();
  }
}

document.addEventListener('DOMContentLoaded', initGoogleSignIn);
