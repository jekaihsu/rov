// Sandboxed Electron preload (sandbox:true) cannot load node:fs / node:path.
// Confirm preload only requires electron, reads edition from argv, and exposes rovDesktop.
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

function loadPreload(argv) {
  let bridge;
  const electron = {
    contextBridge: {
      exposeInMainWorld(name, api) {
        assert.equal(name, 'rovDesktop');
        bridge = api;
      },
      executeInMainWorld() {},
    },
    ipcRenderer: { invoke() {}, send() {} },
  };
  assert.doesNotThrow(() => {
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'preload.cjs'), 'utf8'), {
      require(name) {
        assert.equal(name, 'electron', `sandboxed preload must not require ${name}`);
        return electron;
      },
      process: { argv },
    });
  });
  return bridge;
}

const steam = loadPreload(['electron', '--rov-edition=steam']);
assert.ok(steam, 'window.rovDesktop must be exposed');
assert.equal(steam.edition, 'steam');
assert.equal(typeof steam.steamStatus, 'function');
assert.equal(typeof steam.steamEvent, 'function');
assert.equal(typeof steam.collection, 'function');
assert.equal(typeof steam.saveReport, 'function');

const internal = loadPreload(['electron']);
assert.equal(internal.edition, 'internal');

const ignored = loadPreload(['electron', '--rov-edition=other']);
assert.equal(ignored.edition, 'internal');

console.log('Preload sandbox: edition from argv, no node:fs/path, rovDesktop exposed');
