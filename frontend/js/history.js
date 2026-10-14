/**
 * history.js — Scan history page: paginated table, filter, inline details, export.
 */

let currentPage = 1;
let currentFilter = 'all';
let currentScans = [];
let expandedScanId = null;
let detailCache = {};

async function loadHistory() {
  const perPage = document.getElementById('perPageSelect')?.value || 20;
  try {
    const data = await apiGet(`/history?page=${currentPage}&per_page=${perPage}&filter=${currentFilter}`);
    currentScans = data.scans || [];
    renderFilteredHistory();
    renderPagination(data.pagination || {});
    const count = document.getElementById('historyCount');
    if (count) count.textContent = `${data.pagination.total} total scans`;
  } catch (err) {
    document.getElementById('historyTableBody').innerHTML =
      `<tr><td colspan="6" style="text-align:center;color:var(--danger);padding:2rem;">Error: ${escapeHtml(err.message)}</td></tr>`;
    if (typeof showToast === 'function') showToast(err.message || 'History failed to load.', 'error');
  }
}

function renderFilteredHistory() {
  const q = (document.getElementById('historySearch')?.value || '').trim().toLowerCase();
  const filtered = currentScans.filter(scan => {
    const subject = (scan.email_subject || '').toLowerCase();
    const sender = (scan.email_sender || '').toLowerCase();
    return !q || subject.includes(q) || sender.includes(q);
  });
  renderTable(filtered);
}

function renderTable(scans) {
  const tbody = document.getElementById('historyTableBody');
  if (!tbody) return;
  if (!scans.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-secondary);padding:3rem;">
      No scans found. <a href="scanner.html">Scan your first email</a></td></tr>`;
    return;
  }

  tbody.innerHTML = scans.map(s => historyRow(s)).join('');
  if (expandedScanId && scans.some(s => s.id === expandedScanId)) {
    insertDetailRow(expandedScanId, detailCache[expandedScanId]);
  }
}

function historyRow(s) {
  const score = riskScoreForScan(s);
  const tone = score >= 70 ? 'danger' : score >= 40 ? 'warning' : 'safe';
  return `
    <tr id="scanRow-${s.id}" onclick="openDetail(${s.id})" style="cursor:pointer;">
      <td class="mono" style="font-size:0.78rem;color:var(--text-secondary);">${formatDate(s.scanned_at)}</td>
      <td title="${escapeHtml(s.email_sender || '')}">${escapeHtml(truncateStr(s.email_sender || '-', 28))}</td>
      <td title="${escapeHtml(s.email_subject || '')}">${escapeHtml(truncateStr(s.email_subject || '(no subject)', 34))}</td>
      <td>${predictionBadge(s.prediction)}</td>
      <td>
        <div style="display:flex;align-items:center;gap:10px;">
          <div class="risk-score-track"><span class="risk-score-fill ${tone === 'danger' ? 'fill-danger' : tone === 'safe' ? 'fill-safe' : 'fill-warning'}" style="width:${score}%"></span></div>
          <span class="mono ${tone === 'danger' ? 'text-red' : tone === 'safe' ? 'text-green' : 'text-warning'}" style="font-size:.78rem;">${score}</span>
        </div>
      </td>
      <td>
        <button class="btn btn-ghost btn-sm" type="button" onclick="event.stopPropagation();openDetail(${s.id})">View Details</button>
      </td>
    </tr>
  `;
}

function renderPagination(pag) {
  const bar = document.getElementById('paginationBar');
  if (!bar) return;
  if (pag.pages <= 1) { bar.innerHTML = ''; return; }

  let html = `<button class="btn btn-ghost btn-sm" onclick="goPage(${pag.page-1})" ${!pag.has_prev?'disabled':''}>Prev</button>`;
  for (let p = Math.max(1, pag.page-2); p <= Math.min(pag.pages, pag.page+2); p++) {
    html += `<button class="btn ${p===pag.page?'btn-primary':'btn-ghost'} btn-sm" onclick="goPage(${p})">${p}</button>`;
  }
  html += `<button class="btn btn-ghost btn-sm" onclick="goPage(${pag.page+1})" ${!pag.has_next?'disabled':''}>Next</button>`;
  bar.innerHTML = html;
}

function goPage(p) {
  if (p < 1) return;
  currentPage = p;
  expandedScanId = null;
  loadHistory();
}

function applyFilter(filter) {
  currentFilter = filter;
  currentPage = 1;
  expandedScanId = null;
  ['filterAll','filterPhishing','filterSafe'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    const activeId = `filter${filter.charAt(0).toUpperCase()+filter.slice(1)}`;
    el.classList.toggle('active', el.id === activeId);
  });
  loadHistory();
}

async function openDetail(scanId) {
  if (expandedScanId === scanId) {
    expandedScanId = null;
    renderFilteredHistory();
    return;
  }

  expandedScanId = scanId;
  renderFilteredHistory();
  insertDetailRow(scanId);

  if (detailCache[scanId]) {
    insertDetailRow(scanId, detailCache[scanId]);
    return;
  }

  try {
    const data = await apiGet(`/history/${scanId}`);
    detailCache[scanId] = data.scan;
    insertDetailRow(scanId, data.scan);
  } catch (err) {
    insertDetailRow(scanId, null, err.message);
  }
}

function insertDetailRow(scanId, scan, error) {
  document.querySelectorAll('.history-detail-row').forEach(row => row.remove());
  const baseRow = document.getElementById(`scanRow-${scanId}`);
  if (!baseRow) return;

  const row = document.createElement('tr');
  row.className = 'history-detail-row';
  row.id = `detailRow-${scanId}`;
  row.innerHTML = `<td colspan="6">${detailContent(scan, error)}</td>`;
  baseRow.insertAdjacentElement('afterend', row);
}

function detailContent(scan, error) {
  if (error) {
    return `<div class="history-detail-panel"><div class="alert alert-error">Failed to load details: ${escapeHtml(error)}</div></div>`;
  }
  if (!scan) {
    return `<div class="history-detail-panel"><div class="spinner" style="margin:0 auto;"></div></div>`;
  }

  const keywords = parseKeywords(scan.keywords_flagged);
  return `
    <div class="history-detail-panel">
      <div class="detail-grid">
        <div class="detail-item"><span>Subject</span>${escapeHtml(scan.email_subject || '-')}</div>
        <div class="detail-item"><span>Sender</span>${escapeHtml(scan.email_sender || '-')}</div>
        <div class="detail-item"><span>Confidence</span><span class="mono" style="display:inline;color:var(--text-primary);">${formatConfidence(scan.confidence_score)}</span></div>
        <div class="detail-item"><span>Model</span>${escapeHtml(formatModelName(scan.model_used))}</div>
        <div class="detail-item"><span>URLs</span>${scan.urls_found || 0}</div>
        <div class="detail-item"><span>Suspicious URLs</span><span class="${scan.suspicious_urls > 0 ? 'text-red' : 'text-green'}">${scan.suspicious_urls || 0}</span></div>
        <div class="detail-item"><span>Source</span>${escapeHtml(scan.scan_source || '-')}</div>
        <div class="detail-item"><span>Scanned</span>${formatDate(scan.scanned_at)}</div>
      </div>
      ${keywords.length ? `<div class="mt-4"><div class="keyword-tags">${keywords.map(k=>`<span class="keyword-tag">${escapeHtml(k)}</span>`).join('')}</div></div>` : ''}
      ${scan.email_body_preview ? `<div class="body-preview">${highlightKeywords(escapeHtml(scan.email_body_preview), keywords)}</div>` : ''}
    </div>
  `;
}

function exportHistoryCsv() {
  const q = (document.getElementById('historySearch')?.value || '').trim().toLowerCase();
  const rows = currentScans.filter(scan => {
    const subject = (scan.email_subject || '').toLowerCase();
    const sender = (scan.email_sender || '').toLowerCase();
    return !q || subject.includes(q) || sender.includes(q);
  });

  if (!rows.length) {
    if (typeof showToast === 'function') showToast('No rows to export.', 'error');
    return;
  }

  const headers = ['timestamp', 'sender', 'subject', 'verdict', 'risk_score', 'confidence', 'risk_level'];
  const csv = [
    headers.join(','),
    ...rows.map(s => [
      formatDate(s.scanned_at),
      s.email_sender || '',
      s.email_subject || '',
      s.prediction || '',
      riskScoreForScan(s),
      formatConfidence(s.confidence_score),
      s.risk_level || '',
    ].map(csvCell).join(','))
  ].join('\n');

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `phishguard-history-${new Date().toISOString().slice(0,10)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  if (typeof showToast === 'function') showToast('CSV export ready.', 'success');
}

function closeModal() {
  const modal = document.getElementById('detailModal');
  if (!modal) return;
  modal.classList.add('hidden');
}

function riskScoreForScan(scan) {
  const confidence = Number(scan.confidence_score || 0) * 100;
  return Math.max(0, Math.min(100, Math.round(scan.prediction === 'phishing' ? confidence : 100 - confidence)));
}

function parseKeywords(raw) {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) {
    return [];
  }
}

function highlightKeywords(safeText, keywords) {
  let output = safeText;
  keywords
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .forEach(keyword => {
      output = output.replace(new RegExp(`\\b(${escapeRegExp(escapeHtml(keyword))})\\b`, 'gi'), '<mark class="keyword-highlight">$1</mark>');
    });
  return output;
}

function csvCell(value) {
  return `"${String(value ?? '').replace(/"/g, '""')}"`;
}

function truncateStr(s, n) { return s && s.length > n ? s.slice(0, n) + '...' : (s || '-'); }
function formatModelName(name) { return String(name || '-').replace(/_/g, ' '); }
function escapeRegExp(value) { return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

document.getElementById('detailModal')?.addEventListener('click', e => {
  if (e.target === e.currentTarget) closeModal();
});

loadHistory();
