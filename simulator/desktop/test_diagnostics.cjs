// Oversized or identifying messages must never reach either generation of the local log.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { makeDiagnostics } = require('./diagnostics.cjs');

const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'rov-diagnostics-'));
try {
  const record = makeDiagnostics(folder);
  record('a private user path');
  assert.deepEqual(fs.readdirSync(folder), []);
  for (let i = 0; i < 5000; i++) record('graphics');
  assert.deepEqual(fs.readdirSync(folder).sort(), ['events.log', 'events.log.1']);
  for (const name of fs.readdirSync(folder)) {
    const content = fs.readFileSync(path.join(folder, name), 'utf8');
    assert.ok(content.length <= 65536);
    assert.match(content, /^(?:[\dT:.Z-]+ graphics\n)+$/);
  }
} finally {
  fs.rmSync(folder, { recursive: true, force: true });
}
console.log('Local log allowlist and rotation passed.');
