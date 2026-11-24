import { chromium } from '/workspace/rov_sim/blender_cablecut/npm_three/node_modules/playwright-core/index.mjs';
import { spawn } from 'child_process';
import fs from 'fs';
const OUT = '/workspace/rov_sim/blender_cablecut/e2e'; const PORT = 38080;
const srv = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], { cwd: '/workspace/rov_sim/box_run/viewer', stdio: 'ignore' });
await new Promise((r) => setTimeout(r, 1500));
const exe = fs.readdirSync('/home/box/.cache/ms-playwright').filter((d) => d.startsWith('chromium_headless_shell'))[0];
const browser = await chromium.launch({ executablePath: `/home/box/.cache/ms-playwright/${exe}/chrome-headless-shell-linux64/chrome-headless-shell`,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--enable-webgl', '--ignore-gpu-blocklist', '--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
const errs = [], logs = [];
page.on('pageerror', (e) => errs.push(String(e))); page.on('console', (m) => { if (m.type() === 'error') logs.push(m.text()); });
const g = (f) => page.evaluate(f);
const rep = { checks: {}, shots: [] }; const t0 = Date.now();
try {
  await page.goto(`http://127.0.0.1:${PORT}/cablecut.html${process.env.QS || ''}`, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__game && (window.__game.ready || window.__game.state === 'error'), null, { timeout: 240000 });
  rep.load_s = (Date.now() - t0) / 1000; rep.checks.ready = await g(() => window.__game.ready);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/01_start.png`, timeout: 180000 }); rep.shots.push('01_start.png');
  // controls smoke test
  const p0 = await g(() => window.__game.pos.slice());
  await page.keyboard.down('KeyW'); await page.waitForTimeout(3000); await page.keyboard.up('KeyW');
  const p1 = await g(() => window.__game.pos.slice());
  const y0 = await g(() => window.__game.yaw); await page.keyboard.down('ArrowLeft'); await page.waitForTimeout(1500); await page.keyboard.up('ArrowLeft');
  const y1 = await g(() => window.__game.yaw);
  rep.checks.moved_with_W = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > 0.01; rep.checks.yawed_with_arrow = Math.abs(y1 - y0) > 0.01;
  rep.pos_before = p0; rep.pos_after_W = p1;
  await page.screenshot({ path: `${OUT}/02_approach.png`, timeout: 180000 });
  // go to the cut station
  await g(() => window.__game.teleportToStation());
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/03_holder_moving.png`, timeout: 180000 });
  let ok = false;
  for (let i = 0; i < 150; i++) { // wait for holder + arm
    const s = await g(() => ({ hr: window.__game.holder.ready, ir: window.__game.inRange, st: window.__game.state, t: window.__game.holder.t }));
    if (s.hr && s.ir) { ok = true; break; }
    if (i === 90) await g(() => window.__game.skipHolder());
    await page.waitForTimeout(1000);
  }
  rep.checks.holder_ready_and_inrange = ok;
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/04_before_cut.png`, timeout: 180000 }); rep.shots.push('04_before_cut.png');
  await page.keyboard.press('Space');
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/05_cutting.png`, timeout: 180000 });
  await page.waitForTimeout(4500);
  await page.screenshot({ path: `${OUT}/06_after_cut.png`, timeout: 180000 }); rep.shots.push('06_after_cut.png');
  rep.final_state = await g(() => window.__game.state); rep.checks.severed = rep.final_state === 'done';
  await page.keyboard.press('KeyC'); await page.waitForTimeout(800); await page.screenshot({ path: `${OUT}/07_rov_cam.png`, timeout: 180000 });
  rep.fps = await g(() => window.__game.fps); rep.frames = await g(() => window.__game.frames);
  rep.dom_text_elements = await g(() => [...document.querySelectorAll('.t')].filter((e) => getComputedStyle(e).opacity > 0.05).map((e) => e.id + ':' + e.textContent.slice(0, 60)));
} catch (e) { rep.exception = String(e); }
rep.pageerrors = errs; rep.console_errors = logs.slice(0, 10); rep.total_s = (Date.now() - t0) / 1000;
fs.writeFileSync(`${OUT}/e2e_result.json`, JSON.stringify(rep, null, 1));
console.log(JSON.stringify(rep, null, 1));
await browser.close(); srv.kill();
