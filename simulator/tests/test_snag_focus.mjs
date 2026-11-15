// Assisted snag-focus colouring: off unless enabled, boosts tension near held snag points.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';

const COLOR_STUB = `const THREE = {Color: class {
  constructor(hex) { this.v = {'#e9c534': 0, '#ffb020': 1, '#ff3040': 2}[hex] ?? 0; }
  copy(other) { this.v = other.v; return this; }
  lerp(other, a) { this.v += (other.v - this.v) * a; return this; }
}};`;

const FIDELITY_STUB = `
const values = {snagFocus: false};
export function getFidelity() {
  return {
    get(id) { return values[id]; },
    set(id, value) { values[id] = value; },
  };
}
export function registerFidelityItem() {}
`;

async function loadFocus() {
  const tensionSrc = (await readFile(new URL('../viewer/tether/tension.js', import.meta.url), 'utf8'))
    .replace("import * as THREE from 'three';", COLOR_STUB);
  const tensionUrl = `data:text/javascript;base64,${Buffer.from(tensionSrc).toString('base64')}`;
  const fidelityUrl = `data:text/javascript;base64,${Buffer.from(FIDELITY_STUB).toString('base64')}`;
  let source = await readFile(new URL('../viewer/tether/snag_focus.js', import.meta.url), 'utf8');
  source = source
    .replace("from '../fidelity.js'", `from '${fidelityUrl}'`)
    .replace("from './tension.js'", `from '${tensionUrl}'`);
  const mod = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
  const fidelity = await import(fidelityUrl);
  return {mod, fidelity};
}

const {mod, fidelity} = await loadFocus();
const {snagFocusEnabled, tensionAlong} = mod;

test('snag focus off leaves the spool→ROV blend unchanged', () => {
  fidelity.getFidelity().set('snagFocus', false);
  const tether = {
    tension_spool: 10, tension_rov: 100,
    snags: [{held: true, point: [5, 0, 10], tension_n: 400}],
  };
  const points = [{x: 0, y: -10, z: 5}];
  assert.equal(snagFocusEnabled(), false);
  assert.equal(tensionAlong(tether, 0.5, points), 55);
});

test('assisted focus boosts tension near the hook point', () => {
  fidelity.getFidelity().set('snagFocus', true);
  const tether = {
    tension_spool: 10, tension_rov: 100,
    snags: [{held: true, point: [5, 0, 10], tension_n: 400}],
  };
  const atHook = [{x: 0, y: -10, z: 5}];
  const far = [{x: 20, y: 0, z: 0}];
  assert.equal(snagFocusEnabled(), true);
  assert.ok(tensionAlong(tether, 0, atHook) > 100);
  assert.equal(tensionAlong(tether, 0, far), 10);
});
