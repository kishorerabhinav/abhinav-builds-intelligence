# Detour

A Chrome extension that sends the sites you choose through **your own proxy server**, so you can
open pages that are blocked on your network or in your region. It doesn't include a proxy; point
it at one you run yourself or get from a VPN or proxy provider.

Only use it where you're allowed to. Getting around a school or workplace filter can break that
network's rules.

## Install (Chrome, Edge, Brave)

1. Download and unzip `detour-extension.zip` (or use this folder).
2. Open `chrome://extensions` and turn on **Developer mode** (top right).
3. Click **Load unpacked** and pick the `detour-extension` folder.
4. Pin Detour from the puzzle-piece menu so its icon stays in the toolbar.

## Use

1. Click the Detour icon.
2. Under **Proxy server**, choose the type (HTTP, HTTPS or SOCKS5) and enter the address and port
   your provider gave you, plus the username and password if it has one.
3. Under **Which sites**:
   - **Only these sites**: type one site per line (`example.com` also covers `www.example.com`), or
     open the blocked page and press **Add this tab's site**.
   - **Every site**: all browsing goes through the proxy, except `localhost`.
4. Turn the switch on and press **Save**, then reload the blocked page.

The icon is green while Detour is on and grey when it's off. If the proxy can't be reached, the
popup shows Chrome's last proxy error.

## Good to know

- Chrome can't log in to SOCKS5 proxies with a username and password; use an HTTP/HTTPS proxy
  for those, or a SOCKS5 proxy without a login.
- Your proxy login is kept in Chrome's local extension storage on this computer only.
- Detour changes Chrome's proxy setting. If another extension or your company manages that
  setting, the one with higher priority wins.

## Files

| File | What it does |
|---|---|
| `manifest.json` | Extension definition (Manifest V3) |
| `background.js` | Applies your settings to Chrome's proxy, answers the proxy's login, records errors |
| `shared.js` | Settings, site-list cleanup, and the PAC script that picks which sites use the proxy |
| `popup.html`, `popup.js` | The settings popup |
| `icons/` | Toolbar icons (green on, grey off) |
