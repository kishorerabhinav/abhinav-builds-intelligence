// Settings and proxy rules shared by the background worker and the popup.

// The connection test asks one service for your IP through the proxy and another directly.
export const TEST_PROXIED = "api.ipify.org";
export const TEST_DIRECT = "ifconfig.me";

export const DEFAULTS = {
  enabled: false,
  scheme: "http",        // http | https | socks5
  host: "",
  port: 8080,
  username: "",
  password: "",
  mode: "list",          // list: only the sites below; all: every site except the bypass list
  sites: [],
  bypass: ["localhost", "127.0.0.1", "<local>"],
};

export async function loadSettings() {
  return chrome.storage.local.get(DEFAULTS);
}

/** "https://www.Example.com/path" -> "www.example.com"; returns "" for anything that isn't a host name. */
export function cleanHost(input) {
  let s = String(input || "").trim().toLowerCase();
  if (!s) return "";
  s = s.replace(/^[a-z][a-z0-9+.-]*:\/\//, "");   // scheme
  s = s.split(/[/?#]/)[0];                         // path, query, fragment
  s = s.replace(/^.*@/, "");                       // user info
  s = s.replace(/:\d+$/, "");                      // port
  s = s.replace(/^\*\./, "").replace(/^\./, "");   // "*.example.com" or ".example.com"
  return /^[a-z0-9-]+(\.[a-z0-9-]+)*$/.test(s) ? s : "";
}

export function parseSites(text) {
  const seen = new Set();
  for (const line of String(text || "").split(/[\s,]+/)) {
    const h = cleanHost(line);
    if (h) seen.add(h);
  }
  return [...seen];
}

/** The proxy part of a PAC result, e.g. "PROXY 1.2.3.4:8080". */
export function pacProxy(s) {
  const hp = `${s.host}:${Number(s.port)}`;
  if (s.scheme === "https") return `HTTPS ${hp}`;
  if (s.scheme === "socks5") return `SOCKS5 ${hp}; SOCKS ${hp}`;
  return `PROXY ${hp}`;
}

/** A PAC script that proxies the listed sites (and their subdomains) and sends everything else direct. */
export function buildPac(s) {
  const sites = JSON.stringify([...(s.sites || []), TEST_PROXIED]);
  const proxy = JSON.stringify(pacProxy(s));
  return `function FindProxyForURL(url, host) {
  host = host.toLowerCase();
  var sites = ${sites};
  for (var i = 0; i < sites.length; i++) {
    var site = sites[i];
    if (host === site || dnsDomainIs(host, "." + site)) return ${proxy};
  }
  return "DIRECT";
}`;
}

/** The value passed to chrome.proxy.settings.set, or null to go direct. */
export function proxyConfig(s) {
  if (!s.enabled || !s.host || !Number(s.port)) return null;
  if (s.mode === "all") {
    return {
      mode: "fixed_servers",
      rules: {
        singleProxy: { scheme: s.scheme, host: s.host, port: Number(s.port) },
        bypassList: [...s.bypass, TEST_DIRECT],
      },
    };
  }
  if (!s.sites.length) return null;
  return { mode: "pac_script", pacScript: { data: buildPac(s) } };
}
