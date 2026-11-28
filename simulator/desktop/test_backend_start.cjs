// A missing development interpreter or packaged executable takes the dedicated recovery path.
const assert = require('node:assert/strict');
const path = require('node:path');
const { startBackend } = require('./backend_start.cjs');

async function missingExecutable() {
  const events = [];
  const options = {
    executable: path.join(__dirname, 'missing-test-executable'), prefix: [], options: {},
    record: code => events.push(code), onChild() {},
  };
  await assert.rejects(startBackend(options), { message: 'missing' });
  assert.deepEqual(events, ['missing']);
}
missingExecutable().then(() => console.log('Missing executable recovery passed.'));

async function deniedPorts() {
  const events = [];
  const retries = [];
  const options = {
    allocate() { throw Object.assign(Error(), { code: 'EACCES' }); },
    record: code => events.push(code),
    onRetry: (code, attempt) => retries.push([code, attempt]),
  };
  await assert.rejects(startBackend(options), { message: 'denied' });
  assert.deepEqual(events, ['denied', 'denied', 'denied']);
  assert.deepEqual(retries, [['denied', 2], ['denied', 3]]);
}
deniedPorts().then(() => console.log('Denied loopback ports give bounded retries.'));
