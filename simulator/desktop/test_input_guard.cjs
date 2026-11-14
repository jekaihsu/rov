// Exercise the actual preload-installed gate and the merged input-preference bridge.
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const events = {};
class Socket {
  static OPEN = 1;
  readyState = 1;
  sent = [];
  addEventListener() {}
  send(data) { this.sent.push(JSON.parse(data)); }
}
const page = { window: { WebSocket: Socket }, document: { hasFocus: () => true },
  addEventListener: (name, callback) => { events[name] = callback; } };
let bridge;
const electron = { contextBridge: {
  exposeInMainWorld: (name, api) => { bridge = api; },
  executeInMainWorld: ({ func }) => vm.runInNewContext(`(${func.toString()})()`, page)
}, ipcRenderer: { invoke() {}, send() {} } };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'preload.cjs'), 'utf8'), {
  require: name => {
    assert.equal(name, 'electron');
    return electron;
  }
});
assert.equal(typeof bridge.readInput, 'function');
assert.equal(typeof bridge.rememberInput, 'function');
const socket = new page.window.WebSocket();
function send(seq) {
  socket.send(JSON.stringify({ type: 'rc', seq, controller_generation: 7,
    rc: { left_ud: 1900, keep_depth: 1 } }));
}
send(1);
events.blur();
assert.equal(socket.sent.at(-1).rc.left_ud, 1500);
assert.equal(socket.sent.at(-1).rc.rc_lock, 1);
assert.equal(socket.sent.at(-1).rc.keep_depth, 1);
assert.equal(socket.sent.at(-1).controller_generation, 7);
send(2);
assert.equal(socket.sent.at(-1).rc.left_ud, 1500);
events.pointerdown();
send(3);
assert.equal(socket.sent.at(-1).rc.left_ud, 1900);
events.keydown({ shiftKey: true, code: 'Tab' });
send(4);
assert.equal(socket.sent.at(-1).rc.left_ud, 1500);
console.log('Preload input guard passed: T02 bridge, neutral packets, mode preservation, resume, Shift+Tab.');
