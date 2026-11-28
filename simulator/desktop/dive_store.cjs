// The desktop viewer runs on a fresh HTTP port each launch. Keep compressed dive
// records under userData so their IDs survive an origin change.
const fs = require('node:fs/promises');
const path = require('node:path');
const {randomUUID} = require('node:crypto');

const LIMIT = 48 * 1024 * 1024;
const NAME = /^dive-\d{13}-[0-9a-f-]{36}$/;

function createDiveStore(folder) {
  async function read(id) {
    if (!NAME.test(id)) throw Error('Invalid dive ID');
    const file = path.join(folder, id);
    if ((await fs.stat(file)).size > LIMIT + 5) throw Error('Oversized dive');
    const data = await fs.readFile(file);
    return {version:1, gzip:!!data[0], length:data.readUInt32BE(1), bytes:data.subarray(5)};
  }

  let pending = Promise.resolve();
  function write({gzip, length, bytes}) {
    async function commit() {
      if (!(bytes instanceof ArrayBuffer) || bytes.byteLength > LIMIT || !Number.isSafeInteger(length) ||
          length <= 0 || length > LIMIT) throw Error('Invalid dive');
      await fs.mkdir(folder, {recursive:true});
      const id = 'dive-' + Date.now() + '-' + randomUUID();
      const target = path.join(folder, id);
      const header = Buffer.alloc(5);
      header[0] = Number(!!gzip);
      header.writeUInt32BE(length, 1);
      try {
        await fs.writeFile(target + '.tmp', Buffer.concat([header, Buffer.from(bytes)]), {flag:'wx'});
        await fs.rename(target + '.tmp', target);
      } finally {
        await fs.rm(target + '.tmp', {force:true});
      }
      const records = (await fs.readdir(folder)).filter(name => NAME.test(name)).sort();
      await Promise.all(records.slice(0, -6).map(name => fs.unlink(path.join(folder, name))));
      return id;
    }
    const job = pending.then(commit);
    pending = job.catch(() => {});
    return job;
  }
  async function list() {
    try {
      return (await fs.readdir(folder)).filter(name => NAME.test(name)).sort().reverse();
    } catch (error) {
      if (error.code === 'ENOENT') return [];
      throw error;
    }
  }
  return {read, write, list};
}
module.exports = {createDiveStore};
