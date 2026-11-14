// Compare production payloads under the old and reviewed packaging filters on Linux.
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {packager} = require('@electron/packager');
const asar = require('@electron/asar');
const root = __dirname;
const os = require('node:os');
const assert = require('node:assert/strict');
const output = fs.mkdtempSync(path.join(os.tmpdir(), 'rov-package-audit-'));
console.log('Audit output:', output);
const current = require(root + '/forge.config.cjs').packagerConfig;
async function run() {
  for (const variant of ['before', 'after']) {
    const ignore = variant === 'before' ? [/^\/backend(?:\/|$)/, /^\/out(?:\/|$)/, /\.py$/, /vendor\.cjs$/] : current.ignore;
    const folders = await packager({...current, dir: root, out: path.join(output, variant),
      platform: 'linux', arch: 'x64', electronVersion: '44.5.1', overwrite: true,
      electronZipDir: process.env.ELECTRON_ZIP_DIR, extraResource: [], ignore, prune: true});
    const archive = path.join(folders[0], 'resources/app.asar');
    const list = asar.listPackage(archive).filter(name => !asar.statFile(archive, name).files);
    fs.writeFileSync(path.join(output, `${variant}-files.txt`), list.join('\n') + '\n');
    console.log(variant, 'app.asar bytes:', fs.statSync(archive).size, 'files:', list.length);
    console.log('release docs:', list.filter(name => /RELEASE\.md|vdf\.example/.test(name)));
    if (variant === 'after') {
      assert.ok(!list.some(name => /RELEASE\.md|vdf\.example/.test(name)));
      assert.ok(list.includes('/steam/achievements.json'));
      assert.ok(list.some(name => /steamworks.*\.node$/.test(name)));
      assert.ok(!list.some(name => name.startsWith('/node_modules/three/')));
    }
    console.log('steam catalog:', list.includes('/steam/achievements.json'));
    console.log('native Steam bindings:', list.filter(name => name.endsWith('.node')).length);
    console.log('portable bytes:', execFileSync('du', ['-sb', folders[0]], {encoding: 'utf8'}).trim());
  }
}
run().catch(error => { console.error(error); process.exitCode = 1; });
