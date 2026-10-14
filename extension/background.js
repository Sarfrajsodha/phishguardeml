/**
 * background.js — Chrome Extension Service Worker.
 * Manages extension lifecycle, badge updates, and cross-tab messaging.
 */

const API_BASE = 'http://localhost:5000/api';

// ── Extension installed/updated ────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === 'install') {
    console.log('[PhishGuard] Extension installed successfully.');
    // Set default badge
    chrome.action.setBadgeBackgroundColor({ color: '#00f5ff' });
    chrome.action.setBadgeText({ text: 'AI' });
  }
});

// ── Listen for messages from popup or content scripts ─────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'setBadge') {
    const { text, color } = message;
    chrome.action.setBadgeText({ text, tabId: sender.tab?.id });
    chrome.action.setBadgeBackgroundColor({ color, tabId: sender.tab?.id });
  }

  if (message.action === 'checkHealth') {
    fetch(`${API_BASE}/health`)
      .then(r => r.json())
      .then(data => sendResponse({ ok: true, data }))
      .catch(err => sendResponse({ ok: false, error: err.message }));
    return true; // async
  }
});

// ── Update badge on tab switch to mail pages ───────────────────────────────────
chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  try {
    const tab = await chrome.tabs.get(tabId);
    const isMailPage = tab.url && (
      tab.url.includes('mail.google.com') ||
      tab.url.includes('outlook.live.com') ||
      tab.url.includes('outlook.office.com')
    );
    if (isMailPage) {
      chrome.action.setBadgeText({ text: '✓', tabId });
      chrome.action.setBadgeBackgroundColor({ color: '#00ff88', tabId });
    } else {
      chrome.action.setBadgeText({ text: '', tabId });
    }
  } catch (_) {}
});
