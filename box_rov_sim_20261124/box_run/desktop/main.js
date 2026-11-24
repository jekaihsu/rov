// ROV-01 Simulator desktop shell (Wave 2/3 + Steamworks bridge).
// Serves the bundled viewer over a loopback-only static server (ES modules + importmap need http://),
// opens one window titled "ROV-01 Simulator". `--smoke-shot=<png>` captures the window and quits (CI / xvfb).
const { app, BrowserWindow } = require('electron');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { createSteamBridge } = require('./steam_bridge');

const TITLE = 'ROV-01 Simulator';
function resolveViewerDir() {
  if (process.env.ROV01_VIEWER_DIR) return process.env.ROV01_VIEWER_DIR;
  const candidates = [
    path.resolve(__dirname, 'viewer'),
    path.resolve(__dirname, '..', 'viewer'),
    path.resolve(__dirname, '..', 'box_run', 'viewer'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, 'index.html'))) return c;
  }
  return candidates[2];
}
const VIEWER_DIR = resolveViewerDir();
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.glb': 'model/gltf-binary', '.svg': 'image/svg+xml' };
const arg = (name) => (process.argv.find((a) => a.startsWith(`--${name}=`)) || '').split('=').slice(1).join('=') || null;

const steamBridge = createSteamBridge({ baseDir: __dirname });

function startStatic(root) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const parsed = new URL(req.url, 'http://x');
      if (parsed.pathname === '/api/steam/status') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify(steamBridge.getStatus()));
      }
      if (parsed.pathname === '/api/steam/achievement' && req.method === 'POST') {
        let body = '';
        req.on('data', (chunk) => { body += chunk; });
        req.on('end', () => {
          try {
            const payload = JSON.parse(body || '{}');
            const out = steamBridge.unlockAchievement(payload.id);
            res.writeHead(out.ok ? 200 : 400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(out));
          } catch (e) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ ok: false, error: String(e) }));
          }
        });
        return;
      }
      const rel = decodeURIComponent(parsed.pathname).replace(/^\/+/, '') || 'index.html';
      const file = path.resolve(root, rel);
      if (!file.startsWith(path.resolve(root))) { res.writeHead(403); return res.end(); }
      fs.readFile(file, (err, buf) => {
        if (err) { res.writeHead(404); return res.end('not found'); }
        res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
        res.end(buf);
      });
    });
    srv.listen(0, '127.0.0.1', () => resolve(srv));
  });
}

app.whenReady().then(async () => {
  steamBridge.setRichPresence({ status: 'In Simulator', mission: 'mission_1_pool', depth_m: '0.0' });
  const srv = await startStatic(VIEWER_DIR);
  const port = srv.address().port;
  const win = new BrowserWindow({ width: 1440, height: 900, title: TITLE, backgroundColor: '#090D16',
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true } });
  // keep the product title even if the page sets its own <title>
  win.on('page-title-updated', (e) => { e.preventDefault(); win.setTitle(TITLE); });
  const ws = arg('ws');
  const url = `http://127.0.0.1:${port}/index.html?model=rov01&nointro=1${ws ? `&ws=${encodeURIComponent(ws)}` : ''}`;
  const errors = [];
  win.webContents.on('console-message', (_e, level, msg) => { if (level >= 3) errors.push(msg); });
  await win.loadURL(url).catch((e) => errors.push(String(e)));
  const shot = arg('smoke-shot');
  if (shot) {
    await new Promise((r) => setTimeout(r, 2500));
    const img = await win.webContents.capturePage();
    fs.writeFileSync(path.resolve(__dirname, shot), img.toPNG());
    console.log(JSON.stringify({ smoke: 'ok', title: win.getTitle(), url, shot: path.resolve(__dirname, shot),
      steamMode: steamBridge.getStatus().mode, consoleErrors: errors.length, firstErrors: errors.slice(0, 5) }));
    srv.close();
    app.quit();
  }
});
app.on('window-all-closed', () => app.quit());
