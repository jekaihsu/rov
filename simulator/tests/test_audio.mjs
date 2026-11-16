// Pure audio mappings must remain safe for repeated snapshots and replay resets.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {
  motorParameters, depthCutoff, detectEvents, resolveCue, eventLayer,
  reelParameters, topsideAmbience, layerGains
} from '../viewer/audio/mapping.js';
import {createFidelity} from '../viewer/fidelity.js';
import {UNDERWATER_AUDIO_ID, underwaterAudioEnabled} from '../viewer/audio/fidelity.js';

test('motor output has bounded gain, increasing pitch and reverse timbre', () => {
  assert.equal(motorParameters(0).gain, 0);
  assert.ok(motorParameters(1).frequency > motorParameters(0.25).frequency);
  assert.deepEqual(motorParameters(2), motorParameters(1));
  assert.equal(motorParameters(-1).frequency, motorParameters(1).frequency);
  assert.notEqual(motorParameters(-1).type, motorParameters(1).type);
});

test('depth darkens ambience with finite bounded cutoff', () => {
  assert.equal(depthCutoff(-5), depthCutoff(0));
  assert.ok(depthCutoff(30) < depthCutoff(5));
  assert.ok(depthCutoff(1000) >= 250);
});

test('edges fire once and initial or rewound snapshots stay silent', () => {
  const a = {t: 1, locked: true, photos: 0, tether: {}, events: []};
  const b = {
    ...a, t: 2, locked: false, photos: 1, tether: {warn: true},
    events: [{t: 2, severity: 'hard', obstacle: 'wall'}]
  };
  assert.deepEqual(detectEvents(null, b), []);
  assert.deepEqual(detectEvents(a, b), ['locked', 'photos', 'warn', 'hard']);
  assert.deepEqual(detectEvents(b, structuredClone(b)), []);
  assert.deepEqual(detectEvents(b, a), []);
});

test('warning, completion and control edges preserve severity without repeated beeps', () => {
  const a = {t: 3, battery: 21, score: {}, rc: {right_switch: 0}, tether: {}};
  const b = {
    ...a, t: 4, battery: 20, score: {finished: true}, rc: {right_switch: 2},
    keep_depth: true, tether: {broken: true}
  };
  assert.deepEqual(detectEvents(a, b), ['keep_depth', 'light', 'broken', 'complete', 'warn']);
  assert.deepEqual(detectEvents(b, {...b, t: 5}), []);
});

test('topside system edges cover link, power, thermal, leak, dvl and recording', () => {
  const a = {
    t: 10,
    recording: false,
    link: {state: 'healthy'},
    power: {tripped: false, cutoff: false, limited: false},
    thermal: {warnings: []},
    leak: {detected: false},
    sensors: {dvl: {status: 'locked'}},
    tether: {}
  };
  const b = {
    ...a,
    t: 11,
    recording: true,
    link: {state: 'lost'},
    power: {tripped: true, cutoff: true, limited: true},
    thermal: {warnings: ['motor_hot']},
    leak: {detected: true},
    sensors: {dvl: {status: 'lost'}},
    tether: {warn: true, break_reason: 'gland'}
  };
  assert.deepEqual(detectEvents(a, b), [
    'record_start', 'warn', 'link_lost', 'dvl_lost',
    'power_trip', 'power_cutoff', 'power_limited', 'leak', 'thermal'
  ]);
  const c = {
    ...b, t: 12, recording: false, link: {state: 'healthy'},
    sensors: {dvl: {status: 'locked'}}
  };
  assert.deepEqual(detectEvents(b, c), ['record_stop', 'link_restored', 'dvl_locked']);
});

test('resolveCue routes collisions underwater and alerts topside', () => {
  assert.deepEqual(resolveCue('hard', {}), {kind: 'hard', layer: 'underwater'});
  assert.deepEqual(resolveCue('link_lost', {}), {kind: 'broken', layer: 'topside'});
  assert.deepEqual(resolveCue('record_start', {}), {kind: 'record', layer: 'topside'});
  assert.deepEqual(resolveCue('locked', {locked: true}), {kind: 'confirm', layer: 'topside'});
  assert.equal(eventLayer('severe'), 'underwater');
  assert.equal(eventLayer('dvl_lost'), 'topside');
});

test('reel parameters track powered speed, brake and fairlead friction', () => {
  assert.equal(reelParameters(null).motorGain, 0);
  const haul = reelParameters({mode: 'haul_in', speed: -0.5, stalled: false});
  assert.ok(haul.motorGain > 0);
  assert.ok(haul.fairleadGain > 0);
  assert.ok(haul.motorHz > reelParameters({mode: 'haul_in', speed: -0.1}).motorHz);
  const hold = reelParameters({mode: 'hold', speed: 0, stalled: false});
  assert.ok(hold.brakeGain > 0);
  assert.equal(hold.motorGain, 0);
  const stall = reelParameters({mode: 'haul_in', speed: 0, stalled: true});
  assert.ok(stall.brakeGain > hold.brakeGain);
  assert.ok(topsideAmbience().fanGain > 0);
});

test('underwaterAudio fidelity is off in real and on in assisted', () => {
  const real = createFidelity({edition: null});
  // L3: Steam defaults to real; assisted must be requested explicitly.
  const assisted = createFidelity({search: '?fidelity=assisted'});
  assert.equal(real.get(UNDERWATER_AUDIO_ID), false);
  assert.equal(assisted.get(UNDERWATER_AUDIO_ID), true);
  assert.equal(createFidelity({edition: 'steam'}).get(UNDERWATER_AUDIO_ID), false);
  assert.equal(underwaterAudioEnabled(real), false);
  assert.equal(underwaterAudioEnabled(assisted), true);
  assert.deepEqual(layerGains(false), {topside: 1, underwater: 0});
  assert.deepEqual(layerGains(true), {topside: 1, underwater: 1});
});

test('a photo plays the topside App shutter, never an underwater cue', () => {
  assert.deepEqual(resolveCue('photos', {}), {kind: 'shutter', layer: 'topside'});
  assert.equal(eventLayer('photos'), 'topside');
});
