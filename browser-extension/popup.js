const backendInput = document.querySelector("#backend");
const sessionInput = document.querySelector("#sessionId");
const tokenInput = document.querySelector("#localToken");
const statusElement = document.querySelector("#status");

chrome.storage.local.get(["backend", "sessionId", "localToken"], (stored) => {
  backendInput.value = stored.backend || "http://127.0.0.1:8000";
  sessionInput.value = stored.sessionId || "";
  tokenInput.value = stored.localToken || "";
});

document.querySelector("#save").addEventListener("click", async () => {
  const backend = backendInput.value.trim().replace(/\/$/, "");
  const sessionId = sessionInput.value.trim();
  const localToken = tokenInput.value;
  if (!sessionId || !/^\d+$/.test(sessionId)) {
    statusElement.textContent = "Enter a numeric running session ID.";
    return;
  }
  await chrome.storage.local.set({ backend, sessionId, localToken });
  await chrome.runtime.sendMessage({ type: "connect" });
  statusElement.textContent = "Configuration saved.";
});
