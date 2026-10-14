/**
 * dashboard.js — Dashboard charts, stats, and model status.
 */

let pieChart = null;
let riskChart = null;

async function loadDashboard() {
  try {
    const [stats, health, metrics] = await Promise.all([
      apiGet('/history/stats'),
      apiGet('/health'),
      apiGet('/model-metrics'),
    ]);
    renderStats(stats);
    renderRecentScans(stats.recent_scans || []);
    renderModelStatus(health);
    renderModelMetrics(metrics.metrics || []);
    renderCharts(stats);
  } catch (err) {
    console.error('Dashboard load error:', err);
  }
}

function renderStats(stats) {
  animateCount('statTotal', stats.total_scans || 0);
  animateCount('statPhishing', stats.phishing_count || 0);
  animateCount('statSafe', stats.safe_count || 0);
  animateCount('statRate', stats.phishing_rate || 0, '%', 1);
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val ?? '0';
}

function renderRecentScans(scans) {
  const tbody = document.getElementById('recentScansTable');
  if (!tbody) return;
  if (!scans.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-secondary);padding:2rem;">No scans yet. <a href="scanner.html">Scan your first email</a></td></tr>`;
    return;
  }
  tbody.innerHTML = scans.slice(0, 5).map(s => `
    <tr>
      <td title="${escapeHtml(s.email_subject || '-')}">${escapeHtml(truncate(s.email_subject || '(no subject)', 30))}</td>
      <td>${predictionBadge(s.prediction)}</td>
      <td>${riskBadge(s.risk_level)}</td>
      <td class="mono" style="font-size:0.85rem;">${formatConfidence(s.confidence_score)}</td>
      <td style="font-size:0.82rem;color:var(--text-secondary);">${timeAgo(s.scanned_at)}</td>
    </tr>
  `).join('');
}

function renderModelStatus(health) {
  const el = document.getElementById('modelStatus');
  if (!el) return;
  if (health.models_ready) {
    const modelList = health.models_loaded.map(m =>
      `<div style="display:flex;align-items:center;gap:8px;font-size:0.88rem;margin-bottom:.45rem;">
        <span style="color:var(--safe);">●</span>
        <span style="font-family:var(--font-mono);">${m.replace(/_/g,' ')}</span>
      </div>`
    ).join('');
    el.innerHTML = `<div class="alert alert-success">All models loaded and ready.</div>${modelList}`;
  } else {
    el.innerHTML = `
      <div class="alert alert-error">ML models are not trained yet.</div>
      <p style="font-size:0.85rem;">Go to Admin and retrain models to activate AI detection.</p>`;
  }
}

function renderModelMetrics(metrics) {
  const el = document.getElementById('modelMetrics');
  if (!el || !metrics.length) return;
  // Show most recent metric per model
  const seen = new Set();
  const filtered = metrics.filter(m => { if (seen.has(m.model_name)) return false; seen.add(m.model_name); return true; });
  el.innerHTML = filtered.map(m => `
    <div class="metric-card">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:1rem;">
        <h4>${m.model_name.replace(/_/g,' ')}</h4>
        <span class="mono text-accent">${m.accuracy ? (m.accuracy*100).toFixed(1)+'%' : '-'}</span>
      </div>
      <div class="progress-track">
        <span class="progress-fill progress-warning" style="width:${m.accuracy ? m.accuracy * 100 : 0}%"></span>
      </div>
    </div>
  `).join('');
}

function renderCharts(stats) {
  // ── Pie Chart ─────────────────────────────────────────────
  const pieCtx = document.getElementById('pieChart');
  if (pieCtx) {
    if (pieChart) pieChart.destroy();
    pieChart = new Chart(pieCtx, {
      type: 'doughnut',
      data: {
        labels: ['Phishing', 'Safe'],
        datasets: [{
          data: [stats.phishing_count, stats.safe_count],
          backgroundColor: ['rgba(239,68,68,0.82)', 'rgba(34,197,94,0.72)'],
          borderColor: ['#ef4444', '#22c55e'],
          borderWidth: 2,
          hoverOffset: 8,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#8b949e', font: { family: 'DM Sans' } } },
          tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed} scans` } },
        },
        cutout: '65%',
      },
    });
  }

  // ── Risk Bar Chart ────────────────────────────────────────
  const riskCtx = document.getElementById('riskChart');
  if (riskCtx) {
    if (riskChart) riskChart.destroy();
    const rd = stats.risk_distribution || {};
    riskChart = new Chart(riskCtx, {
      type: 'bar',
      data: {
        labels: ['Safe', 'Low', 'Medium', 'High', 'Critical'],
        datasets: [{
          label: 'Emails',
          data: [rd.safe||0, rd.low||0, rd.medium||0, rd.high||0, rd.critical||0],
          backgroundColor: [
            'rgba(34,197,94,0.64)', 'rgba(230,168,23,0.42)',
            'rgba(245,158,11,0.58)', 'rgba(230,168,23,0.72)', 'rgba(239,68,68,0.78)',
          ],
          borderColor: ['#22c55e','#e6a817','#f59e0b','#e6a817','#ef4444'],
          borderWidth: 1, borderRadius: 6,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#8b949e' }, grid: { color: 'rgba(255,255,255,0.06)' } },
          y: { ticks: { color: '#8b949e', stepSize: 1 }, grid: { color: 'rgba(255,255,255,0.06)' }, beginAtZero: true },
        },
      },
    });
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function animateCount(id, value, suffix = '', decimals = 0) {
  const el = document.getElementById(id);
  if (!el) return;
  const target = Number(value) || 0;
  const duration = 900;
  const start = performance.now();

  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = target * eased;
    el.textContent = `${current.toFixed(decimals)}${suffix}`;
    if (progress < 1) requestAnimationFrame(tick);
  }

  requestAnimationFrame(tick);
}

function truncate(str, n) { return str && str.length > n ? str.slice(0, n) + '...' : str; }

function timeAgo(isoStr) {
  if (!isoStr) return '—';
  const diff = Math.floor((Date.now() - new Date(isoStr + 'Z')) / 1000);
  if (diff < 60)   return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400)return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

// Init
loadDashboard();
