// Verify shutdown ordering without requiring a graphical Electron session.
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { installBackendLifecycle } = require('./backend_lifecycle.cjs');
function fixture() {
  const app = new EventEmitter();
  const backend = new EventEmitter();
  const window = new EventEmitter();
  const failures = [];
  const lifecycle = installBackendLifecycle(app, backend, reason => failures.push(reason));
  lifecycle.watchWindow(window);
  return { app, backend, window, failures, lifecycle };
}
for (const event of ['before-quit', 'window-all-closed']) {
  const test = fixture();
  test.app.emit(event);
  test.backend.emit('exit', 0, null);
  assert.deepEqual(test.failures, []);
}
const closed = fixture();
closed.window.emit('closed');
closed.backend.emit('exit', 0, null);
closed.lifecycle.fail('readiness timeout during shutdown');
closed.app.emit('window-all-closed');
assert.deepEqual(closed.failures, []);
for (const code of [0, 1, null]) {
  const crash = fixture();
  crash.backend.emit('exit', code, code === null ? 'SIGTERM' : null);
  crash.backend.emit('error', Error('duplicate'));
  assert.equal(crash.failures.length, 1);
}
const cancelled = fixture();
cancelled.window.emit('close');
cancelled.backend.emit('exit', 1, null);
assert.equal(cancelled.failures.length, 1);
console.log('Backend lifecycle passed: quit, last-window close, cancelled close, unexpected exit, deduplication.');

const spawnFailure = fixture();
spawnFailure.backend.emit('error', Error('spawn failed'));
spawnFailure.backend.emit('exit', 1, null);
assert.equal(spawnFailure.failures.length, 1);
