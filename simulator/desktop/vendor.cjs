// Install only the modules in the shared viewer dependency manifest.
const fs = require('node:fs');
const path = require('node:path');
const source = path.resolve(path.dirname(require.resolve('three')), '..');
const target = path.resolve(__dirname, '../viewer/vendor/three');
const manifest = require('../tools/vendor-manifest.json');
const files = [...new Set([...manifest.modules, ...manifest.runtime])];
fs.rmSync(target, {recursive: true, force: true});
for (const file of files) {
  const destination = path.join(target, file);
  fs.mkdirSync(path.dirname(destination), {recursive: true});
  fs.copyFileSync(path.join(source, file), destination);
}
console.log('Local Three.js modules ready:', files.length);
