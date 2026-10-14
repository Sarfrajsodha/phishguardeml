/**
 * admin.js — Admin panel: stats, model retraining, user management.
 */

async function loadAdminPage() {
  const user = JSON.parse(localStorage.getItem('phishguard_user') || '{}');
  if (user.role !== 'admin') {
    document.body.innerHTML = `<div class="page" style="margin-left:0;min-height:100vh;display:grid;place-items:center;">
      <div class="card text-center" style="max-width:440px;">
        <h2>Admin Access Required</h2>
        <p class="mt-4">This area is reserved for privileged PhishGuard operators.</p>
        <a href="dashboard.html" class="btn btn-primary mt-6">Go to Dashboard</a>
      </div>
    </div>`;
    return;
  }

  try {
    const [stats, users, metrics] = await Promise.all([
      apiGet('/admin/stats'),
      apiGet('/admin/users'),
      apiGet('/model-metrics'),
    ]);
    renderAdminStats(stats.platform);
    renderAdminScans(stats.recent_scans || []);
    renderUsers(users.users || []);
    renderAdminMetrics(metrics.metrics || []);
  } catch (err) {
    console.error('Admin load error:', err);
    if (typeof showToast === 'function') showToast(err.message || 'Admin data failed to load.', 'error');
  }
}

function renderAdminStats(p) {
  if (!p) return;
  animateAdminCount('aTotalUsers', p.total_users);
  animateAdminCount('aTotalScans', p.total_scans);
  animateAdminCount('aPhishingCount', p.phishing_detected);
  animateAdminCount('aTotalThreats', p.total_threats);
}

function renderAdminScans(scans) {
  const tbody = document.getElementById('adminScansTable');
  if (!tbody) return;
  if (!scans.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-secondary);padding:2rem;">No scans yet.</td></tr>`;
    return;
  }
  tbody.innerHTML = scans.map(s => `
    <tr>
      <td class="mono" style="font-size:0.82rem;color:var(--text-secondary);">#${s.id}</td>
      <td style="font-size:0.82rem;">${escapeHtml(s.user_id)}</td>
      <td title="${escapeHtml(s.email_subject || '')}">${escapeHtml((s.email_subject || '-').slice(0, 34))}</td>
      <td>${predictionBadge(s.prediction)}</td>
      <td>${riskBadge(s.risk_level)}</td>
      <td class="mono" style="font-size:0.85rem;">${formatConfidence(s.confidence_score)}</td>
      <td style="font-size:0.82rem;color:var(--text-secondary);">${formatDate(s.scanned_at)}</td>
    </tr>
  `).join('');
}

function renderUsers(users) {
  const tbody = document.getElementById('usersTable');
  if (!tbody) return;
  if (!users.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-secondary);padding:2rem;">No users found.</td></tr>`;
    return;
  }
  tbody.innerHTML = users.map(u => `
    <tr>
      <td style="font-weight:600;">${escapeHtml(u.username)}</td>
      <td style="font-size:0.85rem;color:var(--text-secondary);">${escapeHtml(u.email)}</td>
      <td class="mono">${u.scan_count ?? u.scans_count ?? '-'}</td>
      <td style="font-size:0.82rem;color:var(--text-secondary);">${formatDate(u.created_at)}</td>
      <td><span class="badge ${u.role === 'admin' ? 'badge-admin' : 'badge-low'}">${escapeHtml(u.role)}</span></td>
      <td>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          <button class="btn btn-ghost btn-sm" onclick="toggleUser(${u.id})">${u.is_active ? 'Disable' : 'Enable'}</button>
          <button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id})">Delete</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function renderAdminMetrics(metrics) {
  const el = document.getElementById('adminModelMetrics');
  if (!el) return;
  if (!metrics.length) {
    el.innerHTML = `<div class="alert alert-info">No metrics yet. Retrain models first.</div>`;
    return;
  }
  const seen = new Set();
  const filtered = metrics.filter(m => {
    if (seen.has(m.model_name)) return false;
    seen.add(m.model_name);
    return true;
  }).slice(0, 3);

  el.innerHTML = filtered.map(m => `
    <div class="metric-card">
      <h4>${escapeHtml(formatModelName(m.model_name))}</h4>
      ${metricRow('Accuracy', m.accuracy)}
      ${metricRow('Precision', m.precision)}
      ${metricRow('Recall', m.recall)}
    </div>
  `).join('');
}

function metricRow(label, value) {
  const percent = value ? value * 100 : 0;
  const tone = percent >= 85 ? 'progress-safe' : percent >= 70 ? 'progress-warning' : 'progress-danger';
  return `
    <div class="metric-row">
      <span>${label}</span>
      <div class="progress-track" style="margin-top:0;"><span class="progress-fill ${tone}" style="width:${percent}%"></span></div>
      <span class="mono">${percent ? percent.toFixed(1) + '%' : '-'}</span>
    </div>
  `;
}

async function toggleUser(userId) {
  try {
    const data = await apiPost(`/admin/users/${userId}/toggle`, {});
    if (typeof showToast === 'function') showToast(data.message || 'User status updated.', 'success');
    loadAdminPage();
  } catch (err) {
    if (typeof showToast === 'function') showToast(err.message || 'User update failed.', 'error');
  }
}

function deleteUser(userId) {
  if (typeof showToast === 'function') {
    showToast(`Delete action is not wired to an API endpoint for user #${userId}.`, 'error');
  }
}

function openRetrainModal() {
  document.getElementById('retrainModal')?.classList.remove('hidden');
}

function closeRetrainModal() {
  document.getElementById('retrainModal')?.classList.add('hidden');
}

function confirmRetrainModel() {
  closeRetrainModal();
  triggerTraining();
}

async function triggerTraining() {
  const btn = document.getElementById('trainBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;"></span><span>Starting...</span>';
  const alertEl = document.getElementById('trainAlert');
  alertEl.innerHTML = '';

  try {
    const data = await apiPost('/train-model', {});
    alertEl.innerHTML = `<div class="alert alert-info">${escapeHtml(data.message)}</div>`;
    btn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;"></span><span>Training...</span>';
    if (typeof showToast === 'function') showToast('Model retraining started.', 'success');
    pollTrainStatus();
  } catch (err) {
    alertEl.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
    btn.disabled = false;
    btn.innerHTML = retrainButtonHtml();
    if (typeof showToast === 'function') showToast(err.message || 'Training failed to start.', 'error');
  }
}

async function checkTrainStatus() { await pollTrainStatus(false); }

async function pollTrainStatus(auto = true) {
  try {
    const data = await apiGet('/train-status');
    const statusEl = document.getElementById('trainStatus');
    const alertEl  = document.getElementById('trainAlert');
    const btn      = document.getElementById('trainBtn');

    if (data.running) {
      statusEl.innerHTML = `<div class="alert alert-info">Training in progress...</div>`;
      if (auto) setTimeout(pollTrainStatus, 4000);
    } else if (data.last_result) {
      if (data.last_result.success) {
        alertEl.innerHTML = `<div class="alert alert-success">Training complete.</div>`;
        renderAdminMetrics(
          Object.entries(data.last_result.metrics || {}).map(([name,m]) => ({ model_name: name, ...m }))
        );
        if (typeof showToast === 'function') showToast('Model retraining complete.', 'success');
      } else {
        alertEl.innerHTML = `<div class="alert alert-error">Training failed: ${escapeHtml(data.last_result.error)}</div>`;
        if (typeof showToast === 'function') showToast('Model retraining failed.', 'error');
      }
      btn.disabled = false;
      btn.innerHTML = retrainButtonHtml();
      statusEl.innerHTML = '';
    } else if (!auto) {
      statusEl.innerHTML = `<div class="alert alert-info">No active training run.</div>`;
    }
  } catch (err) {
    if (!auto && typeof showToast === 'function') showToast(err.message || 'Training status unavailable.', 'error');
  }
}

function retrainButtonHtml() {
  return `<svg class="icon" viewBox="0 0 24 24"><path d="M21 12a9 9 0 0 1-9 9"/><path d="M3 12a9 9 0 0 1 9-9"/><path d="M16 3h-4V1"/><path d="M8 21h4v2"/></svg><span>Retrain Model</span>`;
}

function animateAdminCount(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  const target = Number(value) || 0;
  const duration = 800;
  const start = performance.now();

  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const current = Math.round(target * (1 - Math.pow(1 - progress, 3)));
    el.textContent = current;
    if (progress < 1) requestAnimationFrame(tick);
  }

  requestAnimationFrame(tick);
}

function formatModelName(name) { return String(name || '-').replace(/_/g, ' '); }

document.getElementById('retrainModal')?.addEventListener('click', event => {
  if (event.target === event.currentTarget) closeRetrainModal();
});

loadAdminPage();
