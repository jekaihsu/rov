// Local imported missions and bounded dive recordings. Desktop dives live outside the viewer's ephemeral origin.
function database() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('rov-replays', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('missions');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function writeRecord(id, value, prune) {
  const db = await database();
  try {
    await new Promise((resolve, reject) => {
      const tx = db.transaction('missions', 'readwrite');
      const store = tx.objectStore('missions');
      store.put(value, id);
      const keys = store.getAllKeys();
      keys.onsuccess = () => {
        for (const key of prune(keys.result)) store.delete(key);
      };
      tx.oncomplete = resolve;
      tx.onabort = () => reject(tx.error);
    });
    return id;
  } finally {
    db.close();
  }
}

export function saveReplay(data) {
  const id = crypto.randomUUID();
  return writeRecord(id, data, keys => keys.filter(key => key !== id && !key.startsWith('dive-')));
}

export async function readReplay(id) {
  if (id.startsWith('dive-') && globalThis.rovDesktop?.dive) {
    const record = await rovDesktop.dive('read', id);
    return unpack({...record, body:new Blob([record.bytes])});
  }
  const db = await database();
  try {
    const record = await new Promise((resolve, reject) => {
      const request = db.transaction('missions').objectStore('missions').get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    if (!record) throw Error('Missing replay');
    return id.startsWith('dive-') ? unpack(record) : record;
  } finally {
    db.close();
  }
}

// Completed dives use separate records so importing a mission never evicts a student recording.
const MAX_BYTES = 48 * 1024 * 1024;
export async function saveDive(data) {
  const input = new Blob([JSON.stringify(data)]);
  if (input.size > MAX_BYTES) throw new RangeError('48 MiB');
  const gzip = typeof CompressionStream !== 'undefined';
  const body = gzip ? await new Response(input.stream().pipeThrough(new CompressionStream('gzip'))).blob() : input;
  if (globalThis.rovDesktop?.dive) {
    return rovDesktop.dive('write', {gzip, length:input.size, bytes:await body.arrayBuffer()});
  }
  const id = 'dive-' + Date.now() + '-' + crypto.randomUUID();
  return writeRecord(id, {version:1, gzip, body, length:input.size},
    keys => keys.filter(key => key.startsWith('dive-')).slice(0, -6));
}

async function unpack(record) {
  if (record.version !== 1 || !(record.body instanceof Blob) || record.body.size > MAX_BYTES ||
      !Number.isSafeInteger(record.length) || record.length < 1 || record.length > MAX_BYTES) {
    throw Error('Invalid replay envelope');
  }
  let stream = record.body.stream();
  if (record.gzip) stream = stream.pipeThrough(new DecompressionStream('gzip'));
  const reader = stream.getReader();
  const chunks = [];
  let size = 0;
  for (;;) {
    const {done, value} = await reader.read();
    if (done) break;
    size += value.length;
    if (size > record.length) {
      await reader.cancel();
      throw RangeError('48 MiB');
    }
    chunks.push(value);
  }
  if (size !== record.length) throw Error('EOF');
  return JSON.parse(await new Blob(chunks).text());
}

export function validateReplay(data) {
  function vector(value, size) {
    return Array.isArray(value) && value.length === size && value.every(Number.isFinite);
  }
  function validFrame(frame, index, frames) {
    return Number.isFinite(frame?.t) && (!index || frame.t >= frames[index - 1].t)
      && frame.nav && frame.tether && frame.rc && vector(frame.pos, 3) && vector(frame.q, 4);
  }
  function validClip(clip) {
    return Number.isFinite(clip?.world?.seabed_depth) && clip.world.current && Array.isArray(clip.world.obstacles)
      && Array.isArray(clip.script) && Array.isArray(clip.frames) && clip.frames.length && clip.frames.every(validFrame);
  }
  if ((data?.version != null && data.version !== 2) || !Array.isArray(data?.clips)
      || !data.clips.length || !data.clips.every(validClip)) throw Error('Invalid replay');
  return data;
}

export function diveUrl(id) {
  const url = new URL(location.href);
  for (const key of [...url.searchParams.keys()]) {
    if (!['lang','quality','fidelity'].includes(key)) url.searchParams.delete(key);
  }
  url.searchParams.set('play','1');
  url.searchParams.set('replay','local:' + id);
  url.searchParams.set('nointro','1');
  return url;
}

export async function listDives() {
  if (globalThis.rovDesktop?.dive) return rovDesktop.dive('list');
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction('missions').objectStore('missions').getAllKeys();
      request.onsuccess = () => resolve(request.result.filter(key => key.startsWith('dive-')).reverse());
      request.onerror = () => reject(request.error);
    });
  } finally {
    db.close();
  }
}
