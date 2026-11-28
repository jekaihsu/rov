// Atomic file-backed mirror of viewer localStorage keys under userData/saves/.
// Steam Auto-Cloud syncs this directory (see desktop/steam/RELEASE.md and docs/design/saves.md).
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const { randomUUID } = require('node:crypto');

const MAX_BYTES = 512 * 1024;
const KEY_PATTERN = /^rov\.[A-Za-z0-9._-]{1,96}$/;

function assertKey(key) {
  if (typeof key !== 'string' || !KEY_PATTERN.test(key)) {
    throw new Error('存檔鍵名無效');
  }
  return key;
}

function fileName(key) {
  return `${assertKey(key)}.json`;
}

async function atomicWrite(destination, text) {
  const directory = path.dirname(destination);
  await fsp.mkdir(directory, { recursive: true });
  const temporary = `${destination}.tmp-${randomUUID()}`;
  try {
    const handle = await fsp.open(temporary, 'wx');
    try {
      await handle.writeFile(text, 'utf8');
      await handle.sync();
    } finally {
      await handle.close();
    }
    await fsp.rename(temporary, destination);
  } catch (error) {
    await fsp.unlink(temporary).catch(() => {});
    throw error;
  }
}

class SaveFiles {
  constructor(directory) {
    this.directory = path.resolve(directory);
    this.corruptDirectory = path.join(this.directory, 'corrupt');
    this.queue = Promise.resolve();
  }

  serial(work) {
    const job = this.queue.then(work);
    this.queue = job.catch(() => {});
    return job;
  }

  pathFor(key) {
    return path.join(this.directory, fileName(key));
  }

  async read(key) {
    assertKey(key);
    try {
      const text = await fsp.readFile(this.pathFor(key), 'utf8');
      if (Buffer.byteLength(text) > MAX_BYTES) throw new Error('存檔過大');
      return text;
    } catch (error) {
      if (error.code === 'ENOENT') return null;
      throw error;
    }
  }

  write(key, text) {
    return this.serial(async () => {
      assertKey(key);
      if (typeof text !== 'string') throw new Error('存檔內容必須是字串');
      if (Buffer.byteLength(text) > MAX_BYTES) throw new Error('存檔過大');
      await atomicWrite(this.pathFor(key), text);
      return true;
    });
  }

  backup(key, text) {
    return this.serial(async () => {
      assertKey(key);
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      const destination = path.join(this.corruptDirectory, `${key}.${stamp}.json`);
      const payload = typeof text === 'string' ? text : String(text ?? '');
      await atomicWrite(destination, payload.slice(0, MAX_BYTES));
      return destination;
    });
  }

  readAll() {
    return this.serial(async () => {
      await fsp.mkdir(this.directory, { recursive: true });
      const names = await fsp.readdir(this.directory);
      const out = {};
      for (const name of names) {
        if (!name.endsWith('.json') || name.includes('.tmp-')) continue;
        const key = name.slice(0, -'.json'.length);
        if (!KEY_PATTERN.test(key)) continue;
        try {
          const text = await fsp.readFile(path.join(this.directory, name), 'utf8');
          if (Buffer.byteLength(text) > MAX_BYTES) continue;
          out[key] = text;
        } catch {
          // Skip unreadable files; the viewer falls back to localStorage/defaults.
        }
      }
      return out;
    });
  }
}

function writeSyncAtomic(destination, text) {
  const directory = path.dirname(destination);
  fs.mkdirSync(directory, { recursive: true });
  const temporary = `${destination}.tmp-${randomUUID()}`;
  try {
    fs.writeFileSync(temporary, text, { encoding: 'utf8', flag: 'wx' });
    const fd = fs.openSync(temporary, 'r+');
    try {
      fs.fsyncSync(fd);
    } finally {
      fs.closeSync(fd);
    }
    fs.renameSync(temporary, destination);
  } catch (error) {
    try {
      fs.unlinkSync(temporary);
    } catch {
      // ignore
    }
    throw error;
  }
}

module.exports = { SaveFiles, atomicWrite, writeSyncAtomic, KEY_PATTERN, MAX_BYTES };
