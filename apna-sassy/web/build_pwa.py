# Turns web/index.html into an installable home-screen app (PWA) in web/site/:
# full HTML page + manifest + offline service worker + PNG icons. Run after build.py.
import hashlib, json, os, re
from PIL import Image
W=os.path.dirname(os.path.abspath(__file__))
R=os.path.dirname(W)
OUT=os.path.join(W,'site')
os.makedirs(OUT,exist_ok=True)
page=open(os.path.join(W,'index.html'),encoding='utf-8').read()

icon=Image.open(R+'/docs/app-icon.png').convert('RGB')
for size in (180,192,512):
    icon.resize((size,size),Image.LANCZOS).save(os.path.join(OUT,f'icon-{size}.png'))

page=re.sub(r'<link rel="apple-touch-icon" href="[^"]*">','<link rel="apple-touch-icon" href="icon-180.png">',page)
head=('<!doctype html>\n<html lang="hi">\n<head>\n<meta charset="utf-8">\n'
 '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">\n'
 '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
 '<meta name="theme-color" content="#6ec6ff">\n'
 '<link rel="manifest" href="manifest.webmanifest">\n')
# Reload once when a new version takes over, so an update shows up straight away.
register=('\n<script>\nif ("serviceWorker" in navigator) {\n'
 '  const hadOne = !!navigator.serviceWorker.controller;\n'
 '  navigator.serviceWorker.addEventListener("controllerchange", () => { if (hadOne) location.reload(); });\n'
 '  addEventListener("load", () => navigator.serviceWorker.register("sw.js").then(r => r.update()).catch(() => {}));\n'
 '}\n</script>\n')
page=head+page+register
open(os.path.join(OUT,'index.html'),'w',encoding='utf-8').write(page)

manifest={'name':'अपना सैसी','short_name':'अपना सैसी','start_url':'./','scope':'./',
 'display':'fullscreen','orientation':'landscape','background_color':'#6ec6ff','theme_color':'#6ec6ff',
 'icons':[{'src':f'icon-{s}.png','sizes':f'{s}x{s}','type':'image/png','purpose':'any'} for s in (192,512)]}
open(os.path.join(OUT,'manifest.webmanifest'),'w',encoding='utf-8').write(json.dumps(manifest,ensure_ascii=False,indent=1))

# Cache name changes with the page, so a new build replaces the old offline copy.
version=hashlib.sha256(page.encode()).hexdigest()[:12]
sw=f'''const CACHE = "apna-sassy-{version}";
const CORE = ["./", "index.html", "manifest.webmanifest", "icon-180.png", "icon-192.png", "icon-512.png"];
self.addEventListener("install", e => {{
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
}});
self.addEventListener("activate", e => {{
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
}});
// The page itself: network first so updates arrive, cached copy when offline.
// Everything else: cache first; fonts from Google are cached the first time they load.
self.addEventListener("fetch", e => {{
  if (e.request.method !== "GET") return;
  if (e.request.mode === "navigate") {{
    e.respondWith(fetch(e.request, {{ cache: "no-store" }}).then(res => {{
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put("index.html", copy));
      return res;
    }}).catch(() => caches.match("index.html")));
    return;
  }}
  e.respondWith(caches.match(e.request, {{ ignoreSearch: true }}).then(hit => hit || fetch(e.request).then(res => {{
    const copy = res.clone();
    caches.open(CACHE).then(c => c.put(e.request, copy));
    return res;
  }})));
}});
'''
open(os.path.join(OUT,'sw.js'),'w',encoding='utf-8').write(sw)
print(len(page), sorted(os.listdir(OUT)))
