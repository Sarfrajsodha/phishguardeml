/**
 * scanner.js - Email scanner UI logic.
 * Preserves scan API calls while rendering the Classic Dark Intelligence UI.
 */

let selectedFile = null;
let lastScanBody = '';
let lastScanSender = '';

function switchScanMode(mode) {
  document.getElementById('pasteMode').classList.toggle('hidden', mode !== 'paste');
  document.getElementById('uploadMode').classList.toggle('hidden', mode !== 'upload');
  document.getElementById('tabPaste').classList.toggle('active', mode === 'paste');
  document.getElementById('tabUpload').classList.toggle('active', mode === 'upload');
  resetResults();
}

function fillSample(type) {
  if (type === 'phishing') {
    document.getElementById('emailSubject').value = 'URGENT: Your account has been suspended';
    document.getElementById('emailSender').value = 'security-alert@paypal-verify.tk';
    document.getElementById('emailBody').value =
      `Dear Valued Customer,\n\nWe have detected UNUSUAL ACTIVITY on your PayPal account. ` +
      `Your account has been TEMPORARILY SUSPENDED for security reasons.\n\n` +
      `To restore access IMMEDIATELY, please verify your identity within 24 hours:\n` +
      `http://bit.ly/paypal-verify-now\n\n` +
      `WARNING: Failure to verify will result in PERMANENT account closure.\n\n` +
      `Enter your Social Security Number, credit card details, and password to confirm your identity.\n\n` +
      `Congratulations - you are also eligible for a FREE $500 gift card upon verification.\n\n` +
      `This is your FINAL NOTICE. Act NOW.\n\nPayPal Security Team`;
  } else {
    document.getElementById('emailSubject').value = 'Q2 Team Meeting Recap';
    document.getElementById('emailSender').value = 'manager@company.com';
    document.getElementById('emailBody').value =
      `Hi team,\n\nThank you all for attending the Q2 planning meeting yesterday. ` +
      `The agenda and notes have been uploaded to the shared drive:\n` +
      `https://drive.google.com/drive/folders/company-q2-notes\n\n` +
      `Action items:\n- Alice: finalize budget by May 30\n- Bob: prepare design mockups\n` +
      `- Carol: schedule client demo for June 5\n\nNext meeting is scheduled for June 15 at 10 AM.\n\n` +
      `Best regards,\nDavid`;
  }
}

async function runScan() {
  const body = document.getElementById('emailBody').value.trim();
  const subject = document.getElementById('emailSubject').value.trim();
  const sender = document.getElementById('emailSender').value.trim();
  const model = document.getElementById('modelSelect').value;

  if (!body) {
    showScanError('Email body is required.');
    return;
  }

  lastScanBody = body;
  lastScanSender = sender;
  showScanning();

  try {
    const result = await apiPost('/scan-email', { body, subject, sender, model });
    showResults(result);
  } catch (err) {
    showScanError(err.message || 'Scan failed. Make sure the backend is running.');
  }
}

async function runUploadScan() {
  if (!selectedFile) return;
  lastScanBody = '';
  lastScanSender = selectedFile.name;
  showScanning();

  try {
    const fd = new FormData();
    fd.append('file', selectedFile);
    const result = await apiUpload('/scan-email', fd);
    showResults(result);
  } catch (err) {
    showScanError(err.message || 'Upload scan failed.');
  }
}

function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.add('dragover');
}

function handleDragLeave() {
  document.getElementById('dropZone').classList.remove('dragover');
}

function handleDrop(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) setSelectedFile(file);
}

function handleFileSelect(e) {
  if (e.target.files[0]) setSelectedFile(e.target.files[0]);
}

function setSelectedFile(file) {
  selectedFile = file;
  const info = document.getElementById('fileInfo');
  info.innerHTML = `<span class="mono">${escHtml(file.name)}</span> <span class="text-muted">${(file.size / 1024).toFixed(1)} KB</span>`;
  info.classList.remove('hidden');
  document.getElementById('uploadScanBtn').disabled = false;
}

function showScanning() {
  document.getElementById('defaultResult').classList.add('hidden');
  document.getElementById('scanningResult').classList.remove('hidden');
  document.getElementById('actualResult').classList.add('hidden');

  let w = 0;
  const bar = document.getElementById('scanProgress');
  if (bar) bar.style.width = '0%';
  clearInterval(window._scanInterval);
  window._scanInterval = setInterval(() => {
    w = Math.min(w + Math.random() * 14, 92);
    if (bar) bar.style.width = w + '%';
  }, 240);

  ['scanBtn', 'uploadScanBtn'].forEach(id => {
    const button = document.getElementById(id);
    if (!button) return;
    if (!button.dataset.originalHtml) button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner" style="width:18px;height:18px;"></span> Analyzing threats...';
  });
}

function resetResults() {
  clearInterval(window._scanInterval);
  document.getElementById('defaultResult').classList.remove('hidden');
  document.getElementById('scanningResult').classList.add('hidden');
  document.getElementById('actualResult').classList.add('hidden');
}

function showScanError(msg) {
  clearInterval(window._scanInterval);
  document.getElementById('defaultResult').classList.add('hidden');
  document.getElementById('scanningResult').classList.add('hidden');
  const el = document.getElementById('actualResult');
  el.innerHTML = `<div class="alert alert-error">${escHtml(msg)}</div>`;
  el.classList.remove('hidden');
  resetScanButtons();
  if (typeof showToast === 'function') showToast('Scan failed', msg, 'error');
}

function resetScanButtons() {
  const scanBtn = document.getElementById('scanBtn');
  if (scanBtn) {
    scanBtn.disabled = false;
    scanBtn.innerHTML = scanBtn.dataset.originalHtml || 'Analyze Email';
  }
  const uploadBtn = document.getElementById('uploadScanBtn');
  if (uploadBtn) {
    uploadBtn.disabled = !selectedFile;
    uploadBtn.innerHTML = uploadBtn.dataset.originalHtml || 'Analyze File';
  }
}

function showResults(result) {
  clearInterval(window._scanInterval);
  document.getElementById('scanningResult').classList.add('hidden');

  const isPhishing = result.prediction === 'phishing';
  const confidence = normalizePercent(result.confidence_percent ?? result.confidence ?? result.confidence_score);
  const riskScore = clamp(Math.round(result.risk_score ?? result.risk_percent ?? (isPhishing ? confidence : 100 - confidence)), 0, 100);
  const riskTone = riskScore < 40 ? 'safe' : riskScore < 70 ? 'warning' : 'danger';
  const keywords = result.nlp_analysis?.phishing_keywords || result.keywords || [];
  const urls = result.url_analysis?.urls || [];
  const suspiciousUrls = urls.filter(url => url.is_suspicious);
  const breakdown = buildSignalBreakdown(result, confidence, riskScore);
  const preview = lastScanBody || result.email_body_preview || '';
  const circumference = 339.292;

  const el = document.getElementById('actualResult');
  el.innerHTML = `
    <div class="result-card verdict-${isPhishing ? 'phish' : 'safe'}">
      <div class="result-score-area">
        <div class="donut-wrap" aria-label="Risk score ${riskScore}">
          <svg viewBox="0 0 140 140" aria-hidden="true">
            <circle class="donut-bg" cx="70" cy="70" r="54"></circle>
            <circle class="donut-score c-${isPhishing ? 'phish' : 'safe'}" id="riskDonutScore" cx="70" cy="70" r="54"></circle>
          </svg>
          <div class="donut-center">
            <div class="donut-val">${riskScore}</div>
            <div class="donut-sub">Risk Score</div>
          </div>
        </div>
        <div class="verdict-pill ${isPhishing ? 'phish' : 'safe'}">${isPhishing ? '&#9888; PHISHING' : '&#10003; SAFE'}</div>
        <p class="mono text-muted">Confidence ${confidence.toFixed(1)}%</p>
      </div>

      <div class="breakdown-area">
        <div class="breakdown-grid">
          ${breakdown.cards.map(card => `
            <div class="breakdown-item">
              <div class="breakdown-label">${card.label}</div>
              <div class="breakdown-val ${card.value >= 70 ? 'text-red' : card.value >= 40 ? 'text-orange' : 'text-green'}">${card.value}%</div>
            </div>
          `).join('')}
        </div>
      </div>

      <div class="signals-area">
        <div class="section-label">Signal Progression</div>
        <div class="signal-list">
          ${breakdown.cards.map(card => `
            <div class="signal-row">
              <div class="signal-meta"><span>${card.label}</span><span class="mono">${card.value}%</span></div>
              <div class="signal-track"><div class="signal-fill ${card.value >= 70 ? 'sf-red' : card.value >= 40 ? 'sf-amber' : 'sf-teal'}" style="width:${card.value}%"></div></div>
            </div>
          `).join('')}
        </div>
      </div>

      ${keywords.length ? `
        <div class="preview-area">
          <div class="section-label">Suspicious Keywords</div>
          <div class="keyword-tags">${keywords.map(keyword => `<span class="keyword-tag">${escHtml(keyword)}</span>`).join('')}</div>
        </div>
      ` : ''}

      ${suspiciousUrls.length ? `
        <div class="preview-area">
          <div class="section-label">Suspicious URLs</div>
          ${suspiciousUrls.slice(0, 5).map(item => `
            <div class="url-item suspicious">
              <span>Flag</span>
              <span>${escHtml(item.url || '')}</span>
            </div>
          `).join('')}
        </div>
      ` : ''}

      ${preview ? `
        <div class="preview-area">
          <div class="section-label">Body Preview</div>
          <div class="email-preview">${highlightKeywords(preview, keywords)}</div>
        </div>
      ` : ''}

      ${Object.keys(result.model_breakdown || {}).length > 1 ? `
        <div class="preview-area">
          <div class="section-label">Model Votes</div>
          <div class="keyword-tags">
            ${Object.entries(result.model_breakdown).map(([name, vote]) => `
              <span class="keyword-tag">${escHtml(name.replace(/_/g, ' '))}: ${normalizePercent(vote.confidence).toFixed(1)}%</span>
            `).join('')}
          </div>
        </div>
      ` : ''}

      <div class="result-actions">
        <button class="btn btn-primary btn-sm" onclick="confirmHistorySaved()">
          Save to History
        </button>
        <button class="btn btn-ghost btn-sm" onclick="resetResults();resetScanButtons();">
          New Scan
        </button>
        <a class="btn btn-ghost btn-sm" href="history.html">Open History</a>
      </div>
    </div>
  `;

  el.classList.remove('hidden');
  resetScanButtons();

  requestAnimationFrame(() => {
    const circle = document.getElementById('riskDonutScore');
    if (circle) {
      circle.style.strokeDasharray = String(circumference);
      circle.style.strokeDashoffset = String(circumference);
      requestAnimationFrame(() => {
        circle.style.strokeDashoffset = String(circumference - (circumference * riskScore / 100));
      });
    }
  });

  if (typeof showToast === 'function') {
    showToast('Analysis complete', isPhishing ? 'Threat signals detected.' : 'No high-risk indicators found.', isPhishing ? 'error' : 'success');
  }
}

function confirmHistorySaved() {
  if (typeof showToast === 'function') {
    showToast('Saved to history', 'This scan is available in the history log.', 'success');
  }
}

function buildSignalBreakdown(result, confidence, riskScore) {
  const nlp = result.nlp_analysis || {};
  const url = result.url_analysis || {};
  const sender = lastScanSender || result.sender || '';

  const mlRisk = Math.round(riskScore);
  const keywordRisk = clamp((nlp.phishing_keywords?.length || 0) * 12, 0, 45);
  const urgencyRisk = clamp((nlp.urgency_score || 0) * 10, 0, 45);
  const capsRisk = clamp((nlp.caps_ratio || 0) * 100, 0, 10);
  const nlpRisk = Math.round(clamp(keywordRisk + urgencyRisk + capsRisk, 0, 100));

  const totalUrls = url.total_urls || url.urls?.length || 0;
  const suspiciousCount = url.suspicious_count || (url.urls || []).filter(item => item.is_suspicious).length;
  const urlRisk = Math.round(clamp(
    (totalUrls ? suspiciousCount / totalUrls * 72 : 0) +
    (url.has_http_only ? 10 : 0) +
    (url.has_shortened ? 10 : 0) +
    (url.has_suspicious_tld ? 8 : 0),
    0,
    100
  ));

  const senderRisk = Math.round(clamp(
    (/\.tk|\.zip|\.ru|\.cn|\.top|\.xyz/i.test(sender) ? 42 : 0) +
    (sender.includes('-') ? 16 : 0) +
    (/no-?reply|security|verify|alert/i.test(sender) ? 14 : 0) +
    (!sender.includes('@') && sender ? 18 : 0),
    0,
    100
  ));

  return {
    cards: [
      { label: 'ML Model Score', value: mlRisk || Math.round(confidence) },
      { label: 'NLP Signals', value: nlpRisk },
      { label: 'URL Risk', value: urlRisk },
      { label: 'Sender Risk', value: senderRisk },
    ],
  };
}

function normalizePercent(value) {
  const numeric = Number.parseFloat(value);
  if (!Number.isFinite(numeric)) return 0;
  return clamp(numeric <= 1 ? numeric * 100 : numeric, 0, 100);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function escHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function highlightKeywords(text, keywords) {
  let html = escHtml(text);
  keywords
    .filter(Boolean)
    .sort((a, b) => String(b).length - String(a).length)
    .forEach(keyword => {
      const escapedKeyword = escHtml(keyword);
      const pattern = new RegExp(`(${escapeRegExp(escapedKeyword)})`, 'gi');
      html = html.replace(pattern, '<mark>$1</mark>');
    });
  return html;
}
