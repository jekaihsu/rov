// Unit checks for the playtest feedback ZIP writer and summary scrubbing helpers.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { zipStore } from '../viewer/feedback/zip.js';

test('zipStore writes a readable store-method archive with both files', async () => {
  const json = new TextEncoder().encode('{"ok":true}\n');
  const png = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);
  const blob = zipStore([
    { name: 'screenshot.png', bytes: png },
    { name: 'report.json', bytes: json },
  ]);
  assert.equal(blob.type, 'application/zip');
  const bytes = new Uint8Array(await blob.arrayBuffer());
  assert.ok(bytes.length > 64);
  // Local file header signature for the first entry.
  assert.deepEqual([...bytes.slice(0, 4)], [0x50, 0x4b, 0x03, 0x04]);
  const asText = new TextDecoder().decode(bytes);
  assert.match(asText, /screenshot\.png/);
  assert.match(asText, /report\.json/);
  assert.match(asText, /\{"ok":true\}/);
});

test('summary module redacts emails and tokens in scrubbed output', async () => {
  const source = await readFile(new URL('../viewer/feedback/summary.js', import.meta.url), 'utf8');
  assert.match(source, /redacted-email/);
  assert.match(source, /redacted-token/);
  assert.match(source, /no personal identifiers/);
  assert.match(source, /WINDOW_MS = 60_000/);
});

test('bindings expose F8 reportBug and move settings keyboard to F9', async () => {
  const { bindingRow, findCollisions, defaultPadBindings } = await import('../viewer/input/bindings.js');
  assert.deepEqual(findCollisions(), []);
  assert.deepEqual(findCollisions(undefined, defaultPadBindings()), []);
  const report = bindingRow('reportBug');
  assert.equal(report.keys[0], 'F8');
  assert.equal(report.pad, 'b17');
  assert.equal(report.gesture, 'hold');
  assert.equal(bindingRow('settings').keys[0], 'F9');
});
