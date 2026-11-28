// Exercise the local archive, retention and recorder boundaries without a running simulator or Steam client.
import assert from 'node:assert/strict';
import {mkdtemp, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {createDiveStore} from '../desktop/dive_store.cjs';
import {readReplay, saveDive, validateReplay} from '../viewer/replay_store.js';
import {createFlightLog} from '../viewer/play/flight_log.js';
import {createFidelity} from '../viewer/fidelity.js';
import '../viewer/photo_settings.js';

const world = {scenario:{key:'pool'}, seabed_depth:8, current:{}, obstacles:[]};
const frame = t => ({t, model_id:'pilot', pos:[0,0,1], q:[1,0,0,0], nav:{}, rc:{}, tether:{nodes:[[0,0,0]]}});

test('photo mode follows the edition and switches off with the real preset', () => {
  const preferences = createFidelity({edition:'steam'});
  assert.equal(preferences.get('photoMode'), true);
  preferences.setPreset('real');
  assert.equal(preferences.get('photoMode'), false);
});

test('capture sub-sample snags, collisions and shutter markers and reset them with a dive', () => {
  const log = createFlightLog({getWorld:() => world});
  log.update(frame(1));
  log.update({...frame(1.05), events:[{t:1.05, obstacle:'wall'}], tether:{snagged_on:['wall']}});
  log.photo(1.05);
  log.update(frame(1.3));
  const clip = validateReplay(log.snapshot()).clips[0];
  assert.equal(clip.frames.length, 2);
  assert.deepEqual(clip.debrief.events.map(e => e.kind), ['tether_snag','collision','photo']);
  log.update(frame(0));
  log.update(frame(.3));
  assert.deepEqual(log.snapshot().clips[0].debrief.events, []);
});

test('compressed archives survive reopening, enforce size and reject damaged files', async () => {
  const folder = await mkdtemp(path.join(tmpdir(), 'rov-replay-'));
  try {
    const archive = createDiveStore(folder);
    globalThis.rovDesktop = {dive:(method, value) => archive[method](value)};
    const recording = {version:2, clips:[{world, frames:[frame(0), frame(1)], script:[]}]};
    const id = await saveDive(recording);
    assert.deepEqual(validateReplay(await readReplay(id)), recording);
    await assert.rejects(archive.read('../preferences.json'));
    const payload = {gzip:false, length:1, bytes:new Uint8Array([0]).buffer};
    await assert.rejects(archive.write({...payload, length:49 * 1024 * 1024}));
    await Promise.all(Array.from({length:6}, () => archive.write(payload)));
    await assert.rejects(archive.read(id));
    const damaged = await saveDive(recording);
    await writeFile(path.join(folder, damaged), Buffer.alloc(8));
    await assert.rejects(readReplay(damaged));
    assert.throws(() => validateReplay({clips:[{world, frames:[null]}]}));
  } finally {
    delete globalThis.rovDesktop;
    await rm(folder, {recursive:true, force:true});
  }
});
