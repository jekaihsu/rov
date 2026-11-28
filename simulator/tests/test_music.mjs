// Music context selection, crossfade/ducking state machine and the diveMusic fidelity gate.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, statSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {
  MUSIC_TRACKS, IN_DIVE_CONTEXTS, menuContext, incidentActive, diveContext, musicAllowed, createMusicDirector
} from '../viewer/audio/music.js';
import {createFidelity} from '../viewer/fidelity.js';
import {DIVE_MUSIC_ID, diveMusicEnabled} from '../viewer/audio/music_fidelity.js';

const MUSIC_DIR = fileURLToPath(new URL('../viewer/audio/music/', import.meta.url));
const TWO_MB = 2 * 1024 * 1024;

test('menu screens map to title or briefing music, leaving the menu is silent', () => {
  assert.equal(menuContext('title'), 'title');
  assert.equal(menuContext('main'), 'title');
  assert.equal(menuContext('settings'), 'title');
  assert.equal(menuContext('hangar'), 'briefing');
  assert.equal(menuContext('sites'), 'briefing');
  assert.equal(menuContext('briefing'), 'briefing');
  assert.equal(menuContext(null), null);
});

test('incidents switch the dive to tension and hold it for a while', () => {
  const memory = {};
  assert.equal(diveContext(null, memory), null);
  assert.equal(diveContext({t: 1, tether: {}}, memory), 'dive');
  assert.equal(diveContext({t: 2, tether: {warn: true}}, memory), 'tension');
  assert.equal(diveContext({t: 10, tether: {}}, memory), 'tension');
  assert.equal(diveContext({t: 23, tether: {}}, memory), 'dive');
  assert.equal(diveContext({t: 30, events: [{t: 29, severity: 'severe'}]}, memory), 'tension');
  assert.equal(diveContext({t: 31, score: {finished: true}}, memory), 'results');
});

test('a rewound replay clears the tension hold', () => {
  const memory = {};
  assert.equal(diveContext({t: 50, leak: {detected: true}}, memory), 'tension');
  assert.equal(diveContext({t: 5}, memory), 'dive');
});

test('incident detection covers tether, power, leak, link, thermal and battery', () => {
  assert.equal(incidentActive({}), false);
  assert.equal(incidentActive({tether: {broken: true}}), true);
  assert.equal(incidentActive({tether: {snagged_on: ['pile']}}), true);
  assert.equal(incidentActive({power: {cutoff: true}}), true);
  assert.equal(incidentActive({link: {state: 'lost'}}), true);
  assert.equal(incidentActive({link: {state: 'degraded'}}), false);
  assert.equal(incidentActive({thermal: {warnings: ['motor']}}), true);
  assert.equal(incidentActive({battery: 9}), true);
  assert.equal(incidentActive({battery: 50}), false);
});

test('in-dive music follows the diveMusic fidelity item; menu and results music do not', () => {
  const real = createFidelity({search: '?fidelity=real'});
  const assisted = createFidelity({search: '?fidelity=assisted'});
  assert.equal(diveMusicEnabled(real), false);
  assert.equal(diveMusicEnabled(assisted), true);
  for (const context of IN_DIVE_CONTEXTS) {
    assert.equal(musicAllowed(context, real), false, context);
    assert.equal(musicAllowed(context, assisted), true, context);
  }
  for (const context of ['title', 'briefing', 'results']) assert.equal(musicAllowed(context, real), true, context);
  assert.equal(musicAllowed(null, assisted), false);
  real.set(DIVE_MUSIC_ID, true);
  assert.equal(real.preset, 'custom');
  assert.equal(musicAllowed('dive', real), true);
  const fromUrl = createFidelity({search: '?fidelity=assisted&diveMusic=0'});
  assert.equal(musicAllowed('dive', fromUrl), false);
});

test('changing context crossfades: the old layer fades out while the new one fades in', () => {
  const director = createMusicDirector({fadeSeconds: 2});
  director.setContext('title');
  let output = director.step(0);
  assert.deepEqual(output.started.map(track => track.id), ['title_drone']);
  output = director.step(2);
  assert.equal(output.layers[0].gain, 1);
  assert.equal(director.setContext('title'), false);
  director.setContext('briefing');
  output = director.step(3);
  const gains = Object.fromEntries(output.layers.map(layer => [layer.track.id, layer.gain]));
  assert.equal(gains.title_drone, 0.5);
  assert.equal(gains.briefing_wtc_prelude1, 0.5);
  output = director.step(4);
  assert.deepEqual(output.stopped.map(track => track.id), ['title_drone']);
  assert.deepEqual(output.layers.map(layer => [layer.track.id, layer.gain]), [['briefing_wtc_prelude1', 1]]);
});

test('returning to a fading track picks it back up without restarting it', () => {
  const director = createMusicDirector({fadeSeconds: 2});
  director.setContext('title');
  director.step(0);
  director.step(2);
  director.setContext('briefing');
  director.step(3);
  director.setContext('title');
  const output = director.step(3.5);
  assert.equal(output.started.length, 0);
  const title = output.layers.find(layer => layer.track.id === 'title_drone');
  assert.equal(title.gain, 0.75);
  assert.equal(title.target, 1);
});

test('dive tracks rotate each time the dive context is entered', () => {
  const director = createMusicDirector();
  director.setContext('dive');
  const first = director.current.id;
  director.setContext('tension');
  director.setContext('dive');
  assert.notEqual(director.current.id, first);
  assert.equal(MUSIC_TRACKS.dive.length, 2);
});

test('alerts duck briefly, radio holds the duck, and the release is gradual', () => {
  const director = createMusicDirector({duckLevel: 0.3, duckAttack: 0.2, duckRelease: 1.4});
  director.setContext('title');
  director.step(0);
  director.duckFor(0, 1.2);
  assert.equal(director.step(0.3).duck, 0.3);
  assert.equal(director.step(1).duck, 0.3);
  const releasing = director.step(1.9).duck;
  assert.ok(releasing > 0.3 && releasing < 1, String(releasing));
  assert.equal(director.step(3).duck, 1);
  director.hold(true);
  director.step(3.2);
  assert.equal(director.step(10).duck, 0.3);
  director.hold(false);
  director.step(10);
  assert.equal(director.step(12).duck, 1);
});

test('silence fades every layer out and drops it', () => {
  const director = createMusicDirector({fadeSeconds: 1});
  director.setContext('tension');
  director.step(0);
  director.step(1);
  director.setContext(null);
  const output = director.step(2);
  assert.deepEqual(output.layers, []);
  assert.deepEqual(output.stopped.map(track => track.id), ['tension_peer_gynt_aase']);
});

test('every track file exists, is under 2 MB, and the set stays under 8 MB', () => {
  let total = 0;
  for (const list of Object.values(MUSIC_TRACKS)) {
    for (const track of list) {
      const path = MUSIC_DIR + track.file;
      assert.ok(existsSync(path), track.file);
      const size = statSync(path).size;
      assert.ok(size < TWO_MB, `${track.file} ${size}`);
      total += size;
      assert.ok(track.level > 0 && track.level <= 1, track.id);
    }
  }
  assert.ok(total < 8 * 1024 * 1024, String(total));
});

test('all shipped music and ambience fit the decimal U3 audio budget', async () => {
  const {readdir} = await import('node:fs/promises');
  let total = 0;
  for (const folder of ['music', 'ambience']) {
    const base = new URL('../viewer/audio/' + folder + '/', import.meta.url);
    for (const file of await readdir(base)) {
      if (!file.endsWith('.opus')) continue;
      const size = statSync(new URL(file, base)).size;
      assert.ok(size > 0 && size <= 1_500_000, file);
      total += size;
    }
  }
  assert.ok(total <= 15_000_000, String(total));
});
