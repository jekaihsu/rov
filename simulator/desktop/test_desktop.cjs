// Boundary tests for invalid renderer input and account-specific upload configuration.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { validate } = require('./window_settings.cjs');
const { generate } = require('./steam/generate_vdf.cjs');
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
console.log('Desktop boundaries passed: display validation, VDF rejection and substitution.');
