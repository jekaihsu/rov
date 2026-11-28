// Atomic save file mirror used by the Electron shell for Steam Auto-Cloud.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { SaveFiles, writeSyncAtomic, KEY_PATTERN } = require('./save_files.cjs');

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rov-saves-'));

(async () => {
  try {
    const store = new SaveFiles(path.join(root, 'saves'));
    assert.equal(await store.read('rov.career.v1'), null);
    await store.write('rov.career.v1', JSON.stringify({ version: 1, money: 10 }));
    const text = await store.read('rov.career.v1');
    assert.equal(JSON.parse(text).money, 10);
    assert.ok(fs.existsSync(path.join(root, 'saves', 'rov.career.v1.json')));
    assert.equal(fs.readdirSync(path.join(root, 'saves')).some((name) => name.includes('.tmp-')), false);

    const all = await store.readAll();
    assert.equal(JSON.parse(all['rov.career.v1']).money, 10);

    const corrupt = await store.backup('rov.career.v1', '{broken');
    assert.ok(corrupt.includes(`${path.sep}corrupt${path.sep}`));
    assert.equal(fs.readFileSync(corrupt, 'utf8'), '{broken');

    await assert.rejects(() => store.write('../evil', '{}'));
    await assert.rejects(() => store.write('not-rov', '{}'));
    assert.ok(KEY_PATTERN.test('rov.display.v1'));
    assert.equal(KEY_PATTERN.test('evil'), false);

    const preferences = path.join(root, 'preferences.json');
    writeSyncAtomic(preferences, JSON.stringify({ model: 'x1' }));
    assert.equal(JSON.parse(fs.readFileSync(preferences, 'utf8')).model, 'x1');
    assert.equal(fs.readdirSync(root).some((name) => name.includes('.tmp-')), false);

    console.log('Save files passed: atomic write, readAll, corrupt backup and key guard.');
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
