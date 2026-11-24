// Fidelity profile: preset resolution, URL precedence, custom detection, registration and persistence.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {
  createFidelity, registerFidelityItem, fidelityItems, fidelityText, STORAGE_KEY
} from '../viewer/fidelity.js';

function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return data.has(key) ? data.get(key) : null;
    },
    setItem(key, value) {
      data.set(key, String(value));
    },
    data
  };
}

test('real is the default preset and matches the real vehicle', function () {
  const fidelity = createFidelity();
  assert.equal(fidelity.preset, 'real');
  assert.equal(fidelity.get('assistLevel'), 0);
  assert.equal(fidelity.get('flightProfile'), 'normal');
  assert.equal(fidelity.get('videoDelayMs'), 150);
  assert.equal(fidelity.get('cameraView'), 'onboard');
  assert.equal(fidelity.get('gimbal'), false);
  assert.equal(fidelity.get('thirdPerson'), false);
  assert.equal(fidelity.get('hudDensity'), 1);
  for (const item of fidelityItems()) assert.equal(fidelity.exceeds(item.id), false, item.id);
});
test('assisted preset enables the assists and marks them as exceeding the real vehicle', function () {
  const fidelity = createFidelity({search: '?fidelity=assisted'});
  assert.equal(fidelity.preset, 'assisted');
  assert.equal(fidelity.get('assistLevel'), 2);
  assert.equal(fidelity.get('videoDelayMs'), 0);
  assert.equal(fidelity.get('gimbal'), true);
  assert.equal(fidelity.get('thirdPerson'), true);
  for (const id of ['assistLevel', 'videoDelayMs', 'gimbal', 'thirdPerson']) assert.equal(fidelity.exceeds(id), true);
  assert.equal(fidelity.exceeds('hudDensity'), false);
});
test('edition default applies only without a stored or URL preset', function () {
  assert.equal(createFidelity({edition: 'steam'}).preset, 'assisted');
  assert.equal(createFidelity({edition: 'training'}).preset, 'real');
  assert.equal(createFidelity({edition: 'steam', search: 'fidelity=real'}).preset, 'real');
  const storage = memoryStorage({[STORAGE_KEY]: JSON.stringify({base: 'real', overrides: {}})});
  assert.equal(createFidelity({edition: 'steam', storage}).preset, 'real');
});
test('URL preset wins over stored settings without overwriting them', function () {
  const saved = JSON.stringify({version: 1, base: 'assisted', overrides: {videoDelayMs: 80}});
  const storage = memoryStorage({[STORAGE_KEY]: saved});
  const stored = createFidelity({storage});
  assert.equal(stored.preset, 'custom');
  assert.equal(stored.get('videoDelayMs'), 80);
  const fidelity = createFidelity({storage, search: '?fidelity=real'});
  assert.equal(fidelity.preset, 'real');
  assert.equal(fidelity.get('videoDelayMs'), 150);
  assert.equal(fidelity.get('assistLevel'), 0);
  assert.equal(storage.data.get(STORAGE_KEY), saved);
  assert.equal(createFidelity({storage, search: '?fidelity=bogus'}).get('videoDelayMs'), 80);
});
test('existing URL parameters keep working and win for their own item', function () {
  const storage = memoryStorage({[STORAGE_KEY]: JSON.stringify({base: 'real', overrides: {videoDelayMs: 300}})});
  const fidelity = createFidelity({storage, search: '?fidelity=real&gimbal=1&videoDelayMs=40&cam=chase'});
  assert.equal(fidelity.get('gimbal'), true);
  assert.equal(fidelity.get('videoDelayMs'), 40);
  assert.equal(fidelity.get('cameraView'), 'chase');
  assert.equal(fidelity.get('thirdPerson'), true);
  assert.equal(fidelity.get('assistLevel'), 0);
  assert.equal(fidelity.fromUrl('gimbal'), true);
  assert.equal(fidelity.fromUrl('assistLevel'), false);
  assert.equal(fidelity.preset, 'custom');
  assert.equal(createFidelity({search: 'presentation=assisted&videoDelayMs=500'}).get('videoDelayMs'), 0);
  assert.equal(createFidelity({search: 'presentation=real'}).get('videoDelayMs'), 150);
  assert.equal(createFidelity({search: 'videoDelayMs=5000'}).get('videoDelayMs'), 1000);
  assert.equal(createFidelity({search: 'videoDelayMs=abc&cam=nowhere'}).preset, 'real');
  assert.equal(createFidelity({search: 'fidelity=assisted&gimbal=0'}).get('gimbal'), false);
  assert.equal(createFidelity({search: 'cam=onboard'}).get('thirdPerson'), false);
  assert.equal(createFidelity({search: 'thirdPerson=1'}).get('thirdPerson'), true);
});
test('changing one item makes the profile custom; matching a preset again settles on it', function () {
  const fidelity = createFidelity();
  const seen = [];
  fidelity.subscribe(function record(snapshot, changed) {
    seen.push([snapshot.preset, ...changed]);
  });
  assert.equal(fidelity.set('gimbal', true), true);
  assert.equal(fidelity.preset, 'custom');
  assert.equal(fidelity.set('gimbal', false), true);
  assert.equal(fidelity.preset, 'real');
  assert.deepEqual(seen, [['custom', 'gimbal'], ['real', 'gimbal']]);
  fidelity.set('assistLevel', 2);
  fidelity.set('videoDelayMs', 0);
  fidelity.set('gimbal', true);
  assert.equal(fidelity.preset, 'custom');
  fidelity.set('thirdPerson', true);
  assert.equal(fidelity.preset, 'assisted');
  assert.equal(fidelity.base, 'assisted');
});
test('preference items do not turn a preset into custom', function () {
  const fidelity = createFidelity();
  fidelity.set('hudDensity', 2);
  fidelity.set('flightProfile', 'sport');
  fidelity.set('cameraView', 'chase');
  assert.equal(fidelity.preset, 'real');
  assert.equal(fidelity.get('hudDensity'), 2);
  fidelity.setPreset('real');
  assert.equal(fidelity.get('hudDensity'), 1);
});
test('invalid values and unknown items are rejected without notification', function () {
  const fidelity = createFidelity();
  let calls = 0;
  fidelity.subscribe(function count() {
    calls++;
  });
  assert.equal(fidelity.set('assistLevel', 7), false);
  assert.equal(fidelity.set('gimbal', 'yes'), false);
  assert.equal(fidelity.set('videoDelayMs', 'fast'), false);
  assert.equal(fidelity.set('missing', 1), false);
  assert.equal(fidelity.setPreset('custom'), false);
  assert.equal(fidelity.set('assistLevel', 0), true);
  assert.equal(calls, 0);
  assert.equal(fidelity.set('assistLevel', '1'), true);
  assert.equal(fidelity.get('assistLevel'), 1);
  assert.equal(calls, 1);
});
test('settings persist and round-trip through an injected storage', function () {
  const storage = memoryStorage();
  const first = createFidelity({storage});
  first.setPreset('assisted');
  first.set('videoDelayMs', 120);
  first.set('hudDensity', 0);
  const second = createFidelity({storage});
  assert.equal(second.preset, 'custom');
  assert.equal(second.base, 'assisted');
  assert.equal(second.get('videoDelayMs'), 120);
  assert.equal(second.get('hudDensity'), 0);
  assert.equal(second.get('assistLevel'), 2);
  assert.deepEqual(second.snapshot(), first.snapshot());
  second.setPreset('real');
  assert.deepEqual(JSON.parse(storage.data.get(STORAGE_KEY)), {version: 1, base: 'real', overrides: {}});
  assert.equal(createFidelity({storage}).preset, 'real');
});
test('setSession changes values without writing storage', function () {
  const storage = memoryStorage({
    [STORAGE_KEY]: JSON.stringify({version: 1, base: 'real', overrides: {}}),
  });
  const fidelity = createFidelity({storage});
  assert.equal(fidelity.get('thirdPerson'), false);
  assert.equal(fidelity.setSession('thirdPerson', true), true);
  assert.equal(fidelity.get('thirdPerson'), true);
  assert.deepEqual(JSON.parse(storage.data.get(STORAGE_KEY)), {version: 1, base: 'real', overrides: {}});
});
test('a user change replaces the URL value for that item and persists', function () {
  const storage = memoryStorage();
  const fidelity = createFidelity({storage, search: 'fidelity=assisted&gimbal=0'});
  fidelity.set('gimbal', true);
  assert.equal(fidelity.get('gimbal'), true);
  assert.equal(fidelity.fromUrl('gimbal'), false);
  assert.equal(createFidelity({storage}).preset, 'assisted');
  const urlOnly = createFidelity({storage, search: 'gimbal=0'});
  urlOnly.setPreset('assisted');
  assert.equal(urlOnly.get('gimbal'), true);
});
test('corrupt or unavailable storage falls back to defaults', function () {
  assert.equal(createFidelity({storage: memoryStorage({[STORAGE_KEY]: '{oops'})}).preset, 'real');
  const stale = JSON.stringify({base: 'moon', overrides: {gimbal: 'yes', unknownItem: 3}});
  assert.equal(createFidelity({storage: memoryStorage({[STORAGE_KEY]: stale})}).preset, 'real');
  const broken = {
    getItem() {
      throw new Error('denied');
    },
    setItem() {
      throw new Error('denied');
    }
  };
  const fidelity = createFidelity({storage: broken});
  assert.equal(fidelity.set('gimbal', true), true);
  assert.equal(fidelity.get('gimbal'), true);
});
test('registerFidelityItem adds an item to live stores and enforces the real-preset rule', function () {
  const storage = memoryStorage({[STORAGE_KEY]: JSON.stringify({base: 'real', overrides: {testOverlay: true}})});
  const fidelity = createFidelity({storage});
  const changes = [];
  fidelity.subscribe(function record(snapshot, changed) {
    changes.push(changed);
  });
  assert.equal(fidelity.get('testOverlay'), undefined);
  registerFidelityItem({
    id: 'testOverlay', labelKey: 'testOverlayLabel', type: 'toggle',
    defaults: {real: false, assisted: true}, exceedsReal: true
  }, {testOverlayLabel: '測試疊圖'});
  assert.deepEqual(changes, [['testOverlay']]);
  assert.equal(fidelityText('testOverlayLabel'), '測試疊圖');
  assert.equal(fidelity.get('testOverlay'), true);
  assert.equal(fidelity.exceeds('testOverlay'), true);
  assert.equal(fidelity.preset, 'custom');
  assert.equal(createFidelity().get('testOverlay'), false);
  assert.equal(createFidelity({search: 'fidelity=assisted'}).get('testOverlay'), true);
  assert.throws(function duplicate() {
    registerFidelityItem({id: 'testOverlay', type: 'toggle', defaults: {real: false, assisted: false}});
  }, /already registered/);
  assert.throws(function exceedsInReal() {
    registerFidelityItem({id: 'testBad', type: 'toggle', defaults: {real: true, assisted: true}, exceedsReal: true,
      exceeds(value) {
        return value;
      }});
  }, /must not exceed/);
  assert.throws(function missingDefault() {
    registerFidelityItem({id: 'testIncomplete', type: 'toggle', defaults: {real: false}});
  }, /assisted default/);
  assert.equal(fidelityItems().some(function bad(item) {
    return item.id.startsWith('testBad') || item.id === 'testIncomplete';
  }), false);
});
test('render state follows the fidelity video delay live', async function () {
  const {createRenderState} = await import('../viewer/state_buffer.js');
  const fidelity = createFidelity();
  const rovG = {position: {}, quaternion: {}};
  function place(p, out) {
    out.value = p[0];
  }
  const rig = createRenderState({fidelity, rovG, P: place, Q() {}, fleet: {ingest() {}}, updateTether() {},
    params: new URLSearchParams('presentation=assisted')});
  for (let i = 0; i <= 6; i++) {
    const t = i * .05;
    rig.ingest({t, pos: [t, 0, 0], vel: [1, 0, 0], q: [1, 0, 0, 0]}, false, 10 + t);
  }
  rig.update(null, false, 10.3);
  assert.ok(Math.abs(rovG.position.value - .15) < 1e-9);
  fidelity.setPreset('assisted');
  rig.update(null, false, 10.3);
  assert.ok(Math.abs(rovG.position.value - .325) < 1e-9);
});
