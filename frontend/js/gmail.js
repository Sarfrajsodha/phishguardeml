/* Gmail UI. All mailbox data comes through the authenticated backend API. */
(() => {
  const list = document.getElementById('messageList');
  const status = document.getElementById('mailboxStatus');
  const alert = document.getElementById('gmailAlert');
  const consent = document.getElementById('consentPanel');
  let nextPageToken = '';
  let busy = false;
  const messageCache = new Map();
  let activeOpen = 0;
  let selectedMessage = null;

  function messageError(text) { alert.textContent = text; alert.classList.remove('hidden'); }
  function clearError() { alert.textContent = ''; alert.classList.add('hidden'); }
  function text(tag, value, className) { const el = document.createElement(tag); el.textContent = value || ''; if (className) el.className = className; return el; }

  function fetchMessage(id) {
    if (!messageCache.has(id)) {
      const request = apiGet(`/gmail/messages/${encodeURIComponent(id)}`).then(message => {
        messageCache.set(id, Promise.resolve(message));
        return message;
      }).catch(error => { messageCache.delete(id); throw error; });
      messageCache.set(id, request);
    }
    return messageCache.get(id);
  }

  async function loadMessages(append = false) {
    if (busy) return;
    busy = true; clearError(); status.textContent = append ? 'Loading more messages...' : 'Loading mailbox...';
    try {
      const query = new URLSearchParams({limit: '25'});
      if (append && nextPageToken) query.set('pageToken', nextPageToken);
      const data = await apiGet(`/gmail/messages?${query}`);
      if (!append) list.replaceChildren();
      nextPageToken = data.nextPageToken || '';
      for (const message of data.messages || []) {
        const row = document.createElement('button'); row.type = 'button'; row.className = 'gmail-row';
        const summary = document.createElement('span'); summary.className = 'gmail-row-summary';
        const details = document.createElement('span'); details.className = 'gmail-row-details';
        const hasSubject = Boolean(message.subject && message.subject.trim());
        details.append(text('span', hasSubject ? message.subject : message.snippet, hasSubject ? 'gmail-subject' : 'gmail-snippet'));
        summary.append(text('strong', message.from, 'gmail-sender'), details);
        row.append(summary, text('time', message.date ? new Date(message.date).toLocaleString() : 'Date unavailable', 'gmail-date'));
        row.addEventListener('focus', () => { fetchMessage(message.id).catch(() => {}); }, { once: true });
        row.addEventListener('click', () => openMessage(message)); list.append(row);
      }
      document.getElementById('loadMoreButton').classList.toggle('hidden', !nextPageToken);
      status.textContent = list.children.length ? `${data.resultSizeEstimate || list.children.length} messages in this mailbox` : 'No messages found in this mailbox.';
    } catch (error) {
      status.textContent = '';
      if (error.message.includes('not been authorized') || error.message.includes('Reauthorize')) consent.classList.remove('hidden');
      messageError(error.message || 'Could not load Gmail messages. Please try again.');
    } finally { busy = false; }
  }

  async function checkStatus() {
    try {
      const data = await apiGet('/gmail/status');
      document.getElementById('accountLabel').textContent = `Mailbox linked to ${data.email}`;
      if (!data.authorized) { consent.classList.remove('hidden'); status.textContent = ''; return; }
      consent.classList.add('hidden'); await loadMessages();
    } catch (error) { messageError(error.message || 'Unable to check Gmail authorization.'); status.textContent = ''; }
  }

  async function authorize() {
    const button = document.getElementById('authorizeButton'); button.disabled = true;
    try { const result = await apiPost('/gmail/authorize', {}); window.location.assign(result.url); }
    catch (error) { messageError(error.message || 'Unable to start Gmail authorization.'); button.disabled = false; }
  }

  async function openMessage(summary) {
    const openId = ++activeOpen;
    const panel = document.getElementById('readerPanel');
    const mailPanel = document.querySelector('.gmail-panel');
    const subject = document.getElementById('readerSubject');
    const meta = document.getElementById('readerMeta');
    const plain = document.getElementById('readerPlain');
    const frame = document.getElementById('readerHtml');
    const scanButton = document.getElementById('scanGmailButton');
    selectedMessage = null;
    scanButton.disabled = true;
    document.getElementById('gmailScanStatus').textContent = '';
    document.getElementById('gmailScanResult').hidden = true;
    clearError(); status.textContent = '';
    subject.textContent = summary.subject || '(No subject)';
    meta.textContent = `${summary.from || 'Unknown sender'} | ${summary.date ? new Date(summary.date).toLocaleString() : 'Date unavailable'}`;
    frame.classList.add('hidden'); frame.removeAttribute('srcdoc');
    plain.textContent = 'Loading message...'; plain.classList.remove('hidden');
    mailPanel.classList.add('hidden'); panel.classList.remove('hidden');
    try {
      const message = await fetchMessage(summary.id);
      if (openId !== activeOpen) return;
      selectedMessage = message;
      scanButton.disabled = false;
      subject.textContent = message.subject || '(No subject)';
      meta.textContent = `${message.from || 'Unknown sender'} | ${message.date ? new Date(message.date).toLocaleString() : 'Date unavailable'}`;
      const bodyText = (message.bodyText || '').trim();
      const htmlText = message.bodyHtml ? new DOMParser().parseFromString(message.bodyHtml, 'text/html').body.textContent.trim() : '';
      if (message.bodyHtml && htmlText) {
        plain.classList.add('hidden'); frame.classList.remove('hidden');
        frame.srcdoc = `<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none';"><style>body{font:14px/1.65 Arial,sans-serif;color:#1f2937;padding:20px;overflow-wrap:anywhere}table{max-width:100%;border-collapse:collapse}td,th{padding:5px;vertical-align:top}</style><body>${message.bodyHtml}</body>`;
      } else {
        frame.classList.add('hidden'); frame.removeAttribute('srcdoc');
        plain.textContent = bodyText || message.snippet || '(This message has no readable text content.)';
        plain.classList.remove('hidden');
      }
    } catch (error) {
      if (openId !== activeOpen) return;
      plain.textContent = summary.snippet || 'This message could not be loaded. Please try again.';
      if (error.message.includes('Reauthorize')) consent.classList.remove('hidden');
      messageError(error.message || 'Unable to open this message.');
    }
  }

  function renderGmailScanResult(result) {
    const container = document.getElementById('gmailScanResult');
    const isPhishing = result.prediction === 'phishing';
    const confidence = Number(result.confidence_percent ?? (Number(result.confidence || 0) * 100));
    const riskScore = Math.round(isPhishing ? confidence : 100 - confidence);
    const nlp = result.nlp_analysis || {};
    const urls = result.url_analysis || {};
    const suspiciousUrls = (urls.urls || []).filter(item => item.is_suspicious);
    container.replaceChildren();

    const verdict = document.createElement('div'); verdict.className = 'gmail-scan-verdict';
    const label = document.createElement('strong'); label.className = isPhishing ? 'phishing' : 'safe';
    label.textContent = isPhishing ? 'PHISHING DETECTED' : 'NO HIGH-RISK INDICATORS';
    const model = document.createElement('span'); model.className = 'badge ' + (isPhishing ? 'b-phish' : 'b-safe');
    model.textContent = result.risk_level ? `${result.risk_level} risk` : 'Scan complete';
    verdict.append(label, model); container.append(verdict);

    const metrics = document.createElement('div'); metrics.className = 'gmail-scan-metrics';
    const addMetric = (name, value) => {
      const item = document.createElement('div'); item.className = 'gmail-scan-metric';
      const caption = document.createElement('span'); caption.textContent = name;
      const number = document.createElement('strong'); number.textContent = value;
      item.append(caption, number); metrics.append(item);
    };
    addMetric('Risk score', `${riskScore}/100`);
    addMetric('Confidence', `${confidence.toFixed(1)}%`);
    addMetric('URLs found', String(urls.total_urls || 0));
    addMetric('Suspicious URLs', String(urls.suspicious_count || suspiciousUrls.length));
    container.append(metrics);

    const findings = document.createElement('div'); findings.className = 'gmail-scan-findings';
    const addList = (title, values) => {
      if (!values.length) return;
      const heading = document.createElement('h3'); heading.textContent = title; findings.append(heading);
      const listEl = document.createElement('ul');
      values.forEach(value => { const item = document.createElement('li'); item.textContent = value; listEl.append(item); });
      findings.append(listEl);
    };
    addList('Suspicious keywords', nlp.phishing_keywords || []);
    addList('Suspicious links', suspiciousUrls.map(item => item.url || 'Suspicious URL'));
    if (findings.childElementCount) container.append(findings);
    container.hidden = false;
  }

  async function scanSelectedMessage() {
    if (!selectedMessage) return;
    const button = document.getElementById('scanGmailButton');
    const scanStatus = document.getElementById('gmailScanStatus');
    const originalLabel = button.textContent;
    const message = selectedMessage;
    const parsedHtml = message.bodyHtml ? new DOMParser().parseFromString(message.bodyHtml, 'text/html') : null;
    const htmlBody = parsedHtml ? parsedHtml.body.textContent.trim() : '';
    const htmlLinks = parsedHtml ? Array.from(parsedHtml.querySelectorAll('a[href]'), link => link.href).join(' ') : '';
    const body = [message.bodyText || htmlBody || message.snippet || '', htmlLinks].filter(Boolean).join(' ').trim();
    if (!body) { scanStatus.textContent = 'This email has no readable body to scan.'; return; }
    button.disabled = true; button.textContent = 'Scanning email...'; scanStatus.textContent = 'Analyzing threats';
    try {
      const result = await apiPost('/scan-email', { subject: message.subject || '', sender: message.from || '', body, model: 'ensemble' });
      if (selectedMessage !== message) return;
      renderGmailScanResult(result);
      scanStatus.textContent = 'Analysis complete. This scan was saved to History.';
    } catch (error) {
      scanStatus.textContent = error.message || 'Unable to scan this email.';
    } finally {
      if (selectedMessage === message) { button.disabled = false; button.textContent = originalLabel; }
    }
  }

  document.getElementById('scanGmailButton').addEventListener('click', scanSelectedMessage);
  document.getElementById('authorizeButton').addEventListener('click', authorize);
  document.getElementById('loadMoreButton').addEventListener('click', () => loadMessages(true));
  document.getElementById('refreshButton').addEventListener('click', () => { activeOpen++; messageCache.clear(); nextPageToken = ''; document.getElementById('readerPanel').classList.add('hidden'); document.querySelector('.gmail-panel').classList.remove('hidden'); loadMessages(); });
  document.getElementById('backButton').addEventListener('click', () => { activeOpen++; document.getElementById('readerPanel').classList.add('hidden'); document.querySelector('.gmail-panel').classList.remove('hidden'); });
  const params = new URLSearchParams(location.search);
  if (params.has('gmail_connected')) { messageError('Gmail is authorized for your linked Google account.'); history.replaceState({}, '', location.pathname); }
  if (params.has('gmail_error')) { messageError(params.get('gmail_error') === 'account_mismatch' ? 'The selected Google account does not match the account linked to this website sign-in.' : 'Gmail authorization was not completed. Please try again.'); history.replaceState({}, '', location.pathname); }
  checkStatus();
})();
