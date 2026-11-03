import { loadSettings, parseSites, cleanHost } from "./shared.js";

const $ = id => document.getElementById(id);

function showState(s) {
  const on = s.enabled && s.host && (s.mode === "all" || s.sites.length);
  $("state").textContent = !s.enabled ? "Off"
    : !s.host ? "Add a proxy address"
    : s.mode === "list" && !s.sites.length ? "Add at least one site"
    : s.mode === "all" ? `On for every site via ${s.host}`
    : `On for ${s.sites.length} site${s.sites.length === 1 ? "" : "s"} via ${s.host}`;
  $("state").style.color = on ? "var(--accent)" : "";
}

function showMode() {
  const all = $("modeAll").checked;
  $("sitesLabel").hidden = all;
  $("addCurrent").hidden = all;
}

function read() {
  return {
    enabled: $("enabled").checked,
    scheme: $("scheme").value,
    host: cleanHost($("host").value) || $("host").value.trim(),
    port: Number($("port").value) || 0,
    username: $("username").value.trim(),
    password: $("password").value,
    mode: $("modeAll").checked ? "all" : "list",
    sites: parseSites($("sites").value),
  };
}

function validate(s) {
  if (!s.enabled) return "";
  if (!s.host) return "Enter the proxy server's address.";
  if (!(s.port >= 1 && s.port <= 65535)) return "Enter a port between 1 and 65535.";
  if (s.mode === "list" && !s.sites.length) return "Add at least one site, or choose Every site.";
  return "";
}

async function save() {
  const s = read();
  const problem = validate(s);
  $("error").hidden = !problem;
  $("error").textContent = problem;
  if (problem) return false;
  await chrome.storage.local.set(s);
  $("sites").value = s.sites.join("\n");
  showState(s);
  $("saved").textContent = s.enabled ? "Saved. Reload the page to use it." : "Saved. The extension is off.";
  await chrome.storage.session.remove("lastError");
  return true;
}

async function init() {
  const s = await loadSettings();
  $("enabled").checked = s.enabled;
  $("scheme").value = s.scheme;
  $("host").value = s.host;
  $("port").value = s.port || "";
  $("username").value = s.username;
  $("password").value = s.password;
  (s.mode === "all" ? $("modeAll") : $("modeList")).checked = true;
  $("sites").value = s.sites.join("\n");
  $("socksNote").hidden = s.scheme !== "socks5";
  showMode();
  showState(s);

  const { lastError } = await chrome.storage.session.get("lastError");
  if (lastError && s.enabled) {
    $("error").hidden = false;
    $("error").textContent = `Last proxy error: ${lastError.message}. Check the address, port and login.`;
  }
}

$("save").addEventListener("click", save);
$("enabled").addEventListener("change", async () => {
  if (!(await save())) $("enabled").checked = false;
});
$("scheme").addEventListener("change", () => { $("socksNote").hidden = $("scheme").value !== "socks5"; });
$("modeList").addEventListener("change", showMode);
$("modeAll").addEventListener("change", showMode);
$("addCurrent").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const host = tab && tab.url ? cleanHost(tab.url) : "";
  if (!host) {
    $("error").hidden = false;
    $("error").textContent = "This tab isn't a website, so there's no site to add.";
    return;
  }
  const sites = parseSites($("sites").value);
  if (!sites.includes(host)) sites.push(host);
  $("sites").value = sites.join("\n");
  $("saved").textContent = `Added ${host}. Press Save.`;
});

init();
