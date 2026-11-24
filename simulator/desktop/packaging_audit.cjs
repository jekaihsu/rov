// Inspect actual before/after ASAR archives; this does not validate the separate frozen backend.
const fs = require('node:fs');
const asar = require('@electron/asar');
const assert = require('node:assert/strict');
function inspect(filename) {
  const files = asar.listPackage(filename).filter(file => !asar.statFile(filename, file.slice(1)).files);
  return { archiveBytes: fs.statSync(filename).size, fileCount: files.length,
    firstParty: files.filter(file => !file.startsWith('/node_modules/')).sort() };
}
const before = inspect(process.argv[2]);
const after = inspect(process.argv[3]);
const files = asar.listPackage(process.argv[3]);
assert.deepEqual(after.firstParty, [
  '/THIRD_PARTY_NOTICES.txt', '/backend_lifecycle.cjs', '/collection_store.cjs', '/gpu_preference.cjs',
  '/main.cjs', '/package.json', '/preload.cjs', '/steam/achievements.json', '/steam_service.cjs',
  '/window_settings.cjs'
]);
assert.ok(files.includes('/node_modules/steamworks.js/index.js'));
assert.ok(files.some(file => file.endsWith('steamworksjs.win32-x64-msvc.node')));
assert.ok(files.some(file => file.endsWith('steam_api64.dll')));
assert.ok(files.includes('/node_modules/steamworks.js/LICENSE'));
assert.ok(!files.some(file => file.startsWith('/node_modules/@electron-forge/')));
assert.ok(!files.some(file => file.startsWith('/node_modules/three/')));
const nativeFiles = files.filter(file => /\.(node|dll|so|dylib)$/.test(file));
let nativeBytes = 0;
for (const file of nativeFiles) {
  assert.equal(asar.statFile(process.argv[3], file.slice(1)).unpacked, true);
  const original = asar.extractFile(process.argv[2], file.slice(1));
  const retained = asar.extractFile(process.argv[3], file.slice(1));
  assert.deepEqual(original, retained);
  nativeBytes += retained.length;
}
after.nativeFiles = nativeFiles.length;
after.nativeBytes = nativeBytes;
console.log(JSON.stringify({ before, after, archiveBytesRemoved: before.archiveBytes - after.archiveBytes }, null, 2));
