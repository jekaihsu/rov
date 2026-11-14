// HUD style selection: the camera OSD for the real preset onboard, the line instrument otherwise.
import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveHudStyle } from '../viewer/hud/hud_style.js';
import { createFidelity } from '../viewer/fidelity.js';
import { osdHeadingTape } from '../viewer/hud/osd.js';

test('auto picks the OSD only for the real preset seen from the onboard camera', function () {
  assert.equal(resolveHudStyle({setting: 'auto', preset: 'real', view: 'onboard'}), 'osd');
  assert.equal(resolveHudStyle({setting: 'auto', preset: 'real', view: 'chase'}), 'line');
  assert.equal(resolveHudStyle({setting: 'auto', preset: 'assisted', view: 'onboard'}), 'line');
  assert.equal(resolveHudStyle({setting: 'auto', preset: 'custom', view: 'onboard'}), 'line');
  assert.equal(resolveHudStyle({setting: 'auto', preset: 'real', view: 'cine'}), 'line');
});

test('an explicit style wins over the preset and the view', function () {
  assert.equal(resolveHudStyle({setting: 'line', preset: 'real', view: 'onboard'}), 'line');
  assert.equal(resolveHudStyle({setting: 'osd', preset: 'assisted', view: 'chase'}), 'osd');
  assert.equal(resolveHudStyle({setting: 'bogus', preset: 'real', view: 'onboard'}), 'osd');
});

test('hudStyle is a preset-neutral fidelity item that never exceeds the real vehicle', function () {
  const fidelity = createFidelity();
  assert.equal(fidelity.get('hudStyle'), 'auto');
  assert.equal(fidelity.set('hudStyle', 'line'), true);
  assert.equal(fidelity.preset, 'real');
  assert.equal(fidelity.exceeds('hudStyle'), false);
  assert.equal(fidelity.set('hudStyle', 'glass'), false);
  assert.equal(createFidelity({search: '?hudStyle=osd&fidelity=assisted'}).get('hudStyle'), 'osd');
});

test('the OSD heading tape keeps a fixed width and centres the current heading', function () {
  const widths = new Set();
  for (const heading of [0, 3, 87.6, 181, 259, 359.6]) {
    const plain = osdHeadingTape(heading).replace(/<\/?b>/g, '');
    widths.add(plain.length);
  }
  assert.equal(widths.size, 1);
  assert.match(osdHeadingTape(259), /<b>HDG 259°<\/b>/);
  assert.match(osdHeadingTape(359.6), /<b>HDG 000°<\/b>/);
  assert.match(osdHeadingTape(259), / W /);
});
