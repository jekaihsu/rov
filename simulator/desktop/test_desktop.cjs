// Boundary tests for invalid renderer input and account-specific upload configuration.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { validate, readCurrent, listDisplays } = require('./window_settings.cjs');
const { generate } = require('./steam/generate_vdf.cjs');
const { requestDiscreteGpu } = require('./gpu_preference.cjs');
{
  // Hybrid-graphics laptops: the discrete GPU is requested in both spellings, unless the player opts out.
  const appended = [];
  const fakeApp = { commandLine: { appendSwitch: name => appended.push(name) } };
  requestDiscreteGpu(fakeApp, {});
  assert.deepEqual(appended, ['force-high-performance-gpu', 'force_high_performance_gpu']);
  appended.length = 0;
  assert.deepEqual(requestDiscreteGpu(fakeApp, { ROV_LOW_POWER_GPU: '1' }), []);
  assert.deepEqual(appended, []);
}
assert.throws(() => validate({ mode: 'fullscreen', display: 1, width: -1, height: 800 }));
assert.throws(() => validate({ mode: 'anything', display: 1, width: 1280, height: 800 }));
assert.throws(() => generate({ STEAM_APP_ID: '"escape' }, '/unused'));
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'rov-vdf-'));
try {
  const env = { STEAM_APP_ID: String(100 + 1), STEAM_DEPOT_ID: String(100 + 2) };
  generate(env, temporary);
  const app = fs.readFileSync(path.join(temporary, 'app_build.vdf'), 'utf8');
  assert.ok(!app.includes('REPLACE_WITH'));
  assert.ok(app.includes(env.STEAM_APP_ID));
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
const fakeDisplays = [
  { id: 2, bounds: { x: 0, y: 0, width: 1920, height: 1080 }, workArea: { x: 0, y: 0, width: 1920, height: 1040 } },
  { id: 7, bounds: { x: 1920, y: 0, width: 2560, height: 1440 }, workArea: { x: 1920, y: 0, width: 2560, height: 1400 } },
];
const fakeWindow = {
  getBounds: () => ({ x: 2000, y: 40, width: 1600, height: 900 }),
  isFullScreen: () => false,
  isResizable: () => true,
};
const current = readCurrent(fakeWindow, fakeDisplays, { mode: 'windowed', display: 7, width: 1600, height: 900 });
assert.equal(current.display, 7);
assert.equal(current.mode, 'windowed');
assert.equal(current.width, 1600);
assert.equal(current.height, 900);
const listed = listDisplays({
  getAllDisplays: () => fakeDisplays.map((item) => ({ ...item, displayFrequency: 60 })),
});
assert.equal(listed.length, 2);
assert.equal(listed[1].id, 7);
console.log('Desktop boundaries passed: display validation, current window readout, VDF rejection and substitution.');
