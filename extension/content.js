/**
 * content.js — Chrome Extension content script.
 * Extracts email body, subject, and sender from Gmail and Outlook pages.
 * Injected into mail.google.com and outlook.live.com/office.com.
 */

/** Extract email data from the current Gmail or Outlook page. */
function extractEmailData() {
  const host = window.location.hostname;

  if (host === 'mail.google.com') {
    return extractGmail();
  } else if (host.includes('outlook')) {
    return extractOutlook();
  }
  return null;
}

// ── Gmail extraction ───────────────────────────────────────────────────────────
function extractGmail() {
  // Email body — Gmail uses h7 class for the main content div
  const bodyEl =
    document.querySelector('.a3s.aiL') ||
    document.querySelector('.ii.gt .a3s') ||
    document.querySelector('[data-message-id] .ii.gt');

  const subjectEl = document.querySelector('h2.hP') || document.querySelector('[data-legacy-thread-id]');
  const senderEl  = document.querySelector('.gD') || document.querySelector('[email]');

  return {
    body:    bodyEl?.innerText || bodyEl?.textContent || '',
    subject: subjectEl?.innerText || document.title.replace(' - Gmail','') || '',
    sender:  senderEl?.getAttribute('email') || senderEl?.innerText || '',
    source:  'gmail',
  };
}

// ── Outlook extraction ─────────────────────────────────────────────────────────
function extractOutlook() {
  const bodyEl =
    document.querySelector('[role="main"] [id*="UniqueMessageBody"]') ||
    document.querySelector('.ReadingPaneContent') ||
    document.querySelector('[id*="readingPaneContent"]');

  const subjectEl = document.querySelector('[role="main"] h1') || document.querySelector('.Subject');
  const senderEl  = document.querySelector('[id*="fromLabel"]') || document.querySelector('.fromName');

  return {
    body:    bodyEl?.innerText || '',
    subject: subjectEl?.innerText || '',
    sender:  senderEl?.innerText || '',
    source:  'outlook',
  };
}

// ── Message listener ───────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'extractEmail') {
    const data = extractEmailData();
    sendResponse(data || { error: 'No email content found on this page.' });
  }
  return true; // Keep message channel open for async
});

// ── Floating badge injection (optional) ───────────────────────────────────────
// Adds a small "PhishGuard Active" badge to Gmail/Outlook to show the extension is working
(function injectBadge() {
  if (document.getElementById('phishguard-badge')) return;
  const badge = document.createElement('div');
  badge.id = 'phishguard-badge';
  badge.title = 'PhishGuard AI is active on this page';
  badge.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: rgba(0,245,255,0.1);
    border: 1px solid rgba(0,245,255,0.3);
    color: #00f5ff;
    font-family: system-ui, sans-serif;
    font-size: 11px;
    font-weight: 700;
    padding: 5px 10px;
    border-radius: 50px;
    z-index: 999999;
    pointer-events: none;
    backdrop-filter: blur(4px);
  `;
  badge.textContent = '🛡️ PhishGuard Active';
  document.body?.appendChild(badge);

  // Auto-hide after 4 seconds
  setTimeout(() => badge.remove(), 4000);
})();
