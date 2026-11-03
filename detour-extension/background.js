import { loadSettings, proxyConfig } from "./shared.js";

// Apply the saved settings to Chrome's proxy configuration.
async function apply() {
  const s = await loadSettings();
  const config = proxyConfig(s);
  if (config) {
    await chrome.proxy.settings.set({ value: config, scope: "regular" });
  } else {
    await chrome.proxy.settings.clear({ scope: "regular" });
  }
  const on = !!config;
  const size = n => `icons/${on ? "on" : "off"}-${n}.png`;
  await chrome.action.setIcon({ path: { 16: size(16), 32: size(32) } });
  await chrome.action.setTitle({
    title: on ? `Detour: on (${s.mode === "all" ? "all sites" : s.sites.length + " sites"} via ${s.host})` : "Detour: off",
  });
  await chrome.storage.session.set({ applied: on, appliedAt: Date.now() });
}

chrome.runtime.onInstalled.addListener(apply);
chrome.runtime.onStartup.addListener(apply);
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local") apply();
});

// Remember the last proxy error so the popup can show it.
chrome.proxy.onProxyError.addListener(details => {
  chrome.storage.session.set({ lastError: { message: details.error, details: details.details || "", at: Date.now() } });
});

// Answer the proxy's username/password challenge (HTTP and HTTPS proxies).
// Each request gets one try, so a wrong password can't loop forever.
const tried = new Set();
chrome.webRequest.onAuthRequired.addListener(
  (details, callback) => {
    if (!details.isProxy || tried.has(details.requestId)) {
      callback({});
      return;
    }
    tried.add(details.requestId);
    loadSettings().then(s => {
      if (s.enabled && s.username) {
        callback({ authCredentials: { username: s.username, password: s.password } });
      } else {
        callback({});
      }
    });
  },
  { urls: ["<all_urls>"] },
  ["asyncBlocking"]
);
const forget = details => tried.delete(details.requestId);
chrome.webRequest.onCompleted.addListener(forget, { urls: ["<all_urls>"] });
chrome.webRequest.onErrorOccurred.addListener(forget, { urls: ["<all_urls>"] });
