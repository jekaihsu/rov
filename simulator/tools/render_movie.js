// Render the showcase movie frame by frame and encode it to MP4.
//
//   node tools/render_movie.js --url http://127.0.0.1:8391/index.html --out movie.mp4 \
//        --ffmpeg /path/to/ffmpeg [--fps 24] [--width 1280 --height 720] [--max 6000]
//
// Serve simulator/viewer with any static server first (python -m http.server 8391).
// The page runs in movie + capture mode: nothing advances on its own; each frame this script
// calls window.__advance(1/fps), takes a screenshot and pipes it into ffmpeg, so the result is
// smooth regardless of how slowly the browser renders (software GL is fine).
// Needs Playwright (npm i playwright). Extra flag --three <dir> serves three.js from a local
// node_modules/three instead of the CDN.
const { chromium } = require('playwright');
const { spawn } = require('child_process');

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const url = arg('url', 'http://127.0.0.1:8391/index.html');
const out = arg('out', 'movie.mp4');
const ffmpeg = arg('ffmpeg', 'ffmpeg');
const fps = +arg('fps', 24), W = +arg('width', 1280), H = +arg('height', 720), maxFrames = +arg('max', 6000);
const three = arg('three', null);

(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  page.on('pageerror', (e) => console.error('pageerror:', e.message));
  if (three) {
    await page.route(/cdn\.jsdelivr\.net\/npm\/three@0\.160\.0\/(.*)/, (r) => {
      const m = r.request().url().match(/three@0\.160\.0\/(.*)/);
      r.fulfill({ path: three + '/' + m[1], contentType: 'application/javascript' });
    });
  }
  const sep = url.includes('?') ? '&' : '?';
  await page.goto(`${url}${sep}replay=demo_recording.json&movie&capture`);
  await page.waitForFunction(() => window.__modelLoaded && window.__advance && window.__intro && window.__intro() && window.__intro().playing, null, { timeout: 180000 });
  await page.evaluate(() => document.fonts && document.fonts.ready);

  const enc = spawn(ffmpeg, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  let n = 0;
  for (; n < maxFrames; n++) {
    await page.evaluate((dt) => window.__advance(dt), 1 / fps);
    const jpg = await page.screenshot({ type: 'jpeg', quality: 90 });
    if (!enc.stdin.write(jpg)) await new Promise((r) => enc.stdin.once('drain', r));
    if (n % 120 === 0) {
      const st = await page.evaluate(() => JSON.stringify({ rep: window.__replay && window.__replay() }));
      console.log(`frame ${n} (${(n / fps).toFixed(1)} s video, ${((Date.now() - t0) / 1000).toFixed(0)} s wall) ${st}`);
    }
    if (await page.evaluate(() => window.__movieDone)) break;
  }
  enc.stdin.end();
  await new Promise((r) => enc.on('close', r));
  console.log(`wrote ${out}: ${n + 1} frames, ${((n + 1) / fps).toFixed(1)} s`);
  await browser.close();
})();
