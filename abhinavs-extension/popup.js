import { loadSettings, parseSites, cleanHost, TEST_PROXIED, TEST_DIRECT } from "./shared.js";

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

// Which field to jump to for each problem, so the fix is one tap away.
function fieldFor(s) {
  if (!s.host) return "host";
  if (!(s.port >= 1 && s.port <= 65535)) return "port";
  return "sites";
}

async function save() {
  const s = read();
  const problem = validate(s);
  $("error").hidden = !problem;
  $("error").textContent = problem;
  for (const id of ["host", "port", "sites"]) $(id).classList.remove("missing");
  if (problem) {
    // Say it next to the switch too, where the eye is, and highlight the empty field.
    $("state").textContent = "Can't turn on yet: " + problem.charAt(0).toLowerCase() + problem.slice(1);
    $("state").style.color = "var(--warn)";
    const field = $(fieldFor(s));
    field.classList.add("missing");
    field.focus();
    return false;
  }
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

// ---- Connection test -------------------------------------------------------

async function getIp(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 10000);
  try {
    const res = await fetch(url, { cache: "no-store", signal: ctrl.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = (await res.text()).trim();
    try { return { ip: JSON.parse(text).ip }; } catch (_) { return { ip: text.split(/\s/)[0] }; }
  } catch (e) {
    return { error: e.name === "AbortError" ? "no answer after 10 seconds" : e.message };
  } finally {
    clearTimeout(timer);
  }
}

function addCheck(ok, html) {
  const li = document.createElement("li");
  li.innerHTML = `<span class="${ok ? "ok" : "bad"}">${ok ? "✓" : "✗"}</span><span></span>`;
  li.lastChild.innerHTML = html;
  $("checks").appendChild(li);
}
const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function runTest() {
  $("test").disabled = true;
  $("test").textContent = "Testing…";
  $("checks").innerHTML = "";
  $("checks").hidden = false;
  $("verdict").hidden = true;
  const s = await loadSettings();
  let verdict = "";

  // 1. Who controls Chrome's proxy setting?
  const setting = await chrome.proxy.settings.get({ incognito: false });
  const control = setting.levelOfControl;
  const ours = control === "controlled_by_this_extension";
  if (ours) addCheck(true, "Chrome is using this extension's proxy settings.");
  else if (control === "controlled_by_other_extensions") {
    addCheck(false, "Another extension (probably a VPN or proxy extension) controls Chrome's proxy. Turn it off in chrome://extensions.");
    verdict = verdict || "Turn off the other VPN or proxy extension, then test again.";
  } else if (control === "not_controllable") {
    addCheck(false, "Your computer's administrator or a policy controls Chrome's proxy, so no extension can change it.");
    verdict = verdict || "This Chrome is managed, so the extension can't take over the proxy.";
  } else {
    addCheck(false, s.enabled ? "The extension is on but its setting isn't applied. Press Save." : "The extension is off. Turn the switch on.");
    verdict = verdict || (s.enabled ? "Press Save, then test again." : "Turn the switch on, then test again.");
  }

  // 2. Your normal IP, and 3. your IP through the proxy
  const [direct, proxied] = await Promise.all([getIp(`https://${TEST_DIRECT}/ip`), getIp(`https://${TEST_PROXIED}/?format=json`)]);
  if (direct.ip) addCheck(true, `Your normal IP: <code>${esc(direct.ip)}</code>`);
  else addCheck(false, `Couldn't read your normal IP (${esc(direct.error)}).`);

  if (!ours) {
    addCheck(false, "Proxy not tested, because Chrome isn't using this extension's settings yet.");
  } else if (proxied.ip && direct.ip && proxied.ip !== direct.ip) {
    addCheck(true, `IP through the proxy: <code>${esc(proxied.ip)}</code>. The proxy works.`);
    verdict = verdict || "The proxy works. If a site still won't open, check it's in the list (or use Every site), and that this proxy allows that site.";
  } else if (proxied.ip && direct.ip && proxied.ip === direct.ip) {
    addCheck(false, `IP through the proxy is the same as your normal IP (<code>${esc(proxied.ip)}</code>), so traffic isn't going through the proxy.`);
    verdict = verdict || "Traffic isn't going through the proxy. Check the steps marked ✗ above.";
  } else if (proxied.ip) {
    addCheck(true, `IP through the proxy: <code>${esc(proxied.ip)}</code>.`);
  } else {
    const { lastError } = await chrome.storage.session.get("lastError");
    const why = lastError ? `${lastError.message}` : proxied.error;
    addCheck(false, `The proxy didn't respond (${esc(why)}).`);
    verdict = verdict || "The proxy isn't working: check its type, address, port and login, or try another proxy. Many free proxies are offline or don't support HTTPS sites.";
  }

  $("verdict").textContent = verdict;
  $("verdict").hidden = !verdict;
  $("test").disabled = false;
  $("test").textContent = "Test again";
}
$("test").addEventListener("click", runTest);

init();
