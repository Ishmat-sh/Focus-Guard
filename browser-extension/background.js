const HTTP_PROTOCOLS = new Set(["http:", "https:"]);

async function reportActiveDomain() {
  const stored = await chrome.storage.local.get(["backend", "sessionId", "localToken"]);
  if (!stored.backend || !stored.sessionId || !stored.localToken) return;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url) return;

  let url;
  try {
    url = new URL(tab.url);
  } catch {
    return;
  }
  if (!HTTP_PROTOCOLS.has(url.protocol)) return;

  const endpoint =
    `${stored.backend}/sessions/${encodeURIComponent(stored.sessionId)}/context/browser`;
  try {
    await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Focus-Guard-Token": stored.localToken,
      },
      body: JSON.stringify({ domain: url.hostname }),
    });
  } catch {
    // The local bridge is optional and must fail silently.
  }
}

chrome.tabs.onActivated.addListener(reportActiveDomain);
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete") reportActiveDomain();
});
chrome.runtime.onInstalled.addListener(reportActiveDomain);
chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "connect") reportActiveDomain();
});
