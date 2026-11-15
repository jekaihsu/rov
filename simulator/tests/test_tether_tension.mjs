// Tension gauge colours follow the host's rated working loads; older hosts keep the 250 N level.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';

// Minimal Color stand-in: one channel is enough to tell low / warn / break colours apart.
const COLOR_STUB = `const THREE = {Color: class {
  constructor(hex) { this.v = {'#e9c534': 0, '#ffb020': 1, '#ff3040': 2}[hex] ?? 0; }
  copy(other) { this.v = other.v; return this; }
  lerp(other, a) { this.v += (other.v - this.v) * a; return this; }
}};`;

async function tensionModule() {
  const source = (await readFile(new URL('../viewer/tether/tension.js', import.meta.url), 'utf8'))
    .replace("import * as THREE from 'three';", COLOR_STUB);
  return import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
}

const {LEGACY_WARN_N, tensionColor, warnLoad, gaugePercent} = await tensionModule();

test('warning levels come from the working loads when the host sends them', () => {
  const tether = {working_load_n: 1471.5, gland_working_load_n: 444.6};
  assert.equal(warnLoad(tether), 1471.5);
  assert.equal(warnLoad(tether, 'tension_spool'), 1471.5);
  assert.equal(warnLoad(tether, 'tension_rov'), 444.6);
  assert.equal(warnLoad({}, 'tension_rov'), LEGACY_WARN_N);
  assert.equal(warnLoad(undefined), LEGACY_WARN_N);
});

test('300 N is a warning colour only on hosts without working loads', () => {
  const out = {v: 0, copy(o) { this.v = o.v; return this; }, lerp(o, a) { this.v += (o.v - this.v) * a; return this; }};
  assert.ok(tensionColor(300, out).v > 1);                         // legacy: past the 250 N warning
  assert.ok(tensionColor(300, out, 1471.5).v < 1);                 // rated load: still below warning
  assert.equal(tensionColor(1471.5, out, 1471.5).v, 1);
  assert.ok(gaugePercent(1e6) === 100 && gaugePercent(0) === 0);
});
