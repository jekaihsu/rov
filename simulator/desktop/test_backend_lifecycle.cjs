// Exercise desktop shutdown event orderings without requiring Electron or Steam.
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const {watchBackend} = require('./backend_lifecycle.cjs');
function fixture() {
  const app = new EventEmitter();
  const window = new EventEmitter();
  const backend = new EventEmitter();
  const failures = [];
  watchBackend(app, window, backend, reason => failures.push(reason));
  return {app, window, backend, failures};
}
for (const event of ['closed', 'before-quit']) {
  const test = fixture();
  (event === 'closed' ? test.window : test.app).emit(event);
  test.backend.emit('exit', 0, null);
  assert.deepEqual(test.failures, []);
}
for (const code of [0, 1]) {
  const test = fixture();
  test.backend.emit('exit', code, null);
  assert.equal(test.failures.length, 1);
}
const test = fixture();
test.backend.emit('error', Error('spawn failed'));
test.backend.emit('exit', 1, null);
assert.equal(test.failures.length, 1);
console.log('Backend lifecycle passed: window close, quit, unexpected exit and spawn failure.');
