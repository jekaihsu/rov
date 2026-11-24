// Exercise Steam mock fallback, catalogue allowlists, presence and cloud path constants without Steam.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createSteam } = require('./steam_service.cjs');
const { createSteam: createBridge } = require('./steam_bridge.cjs');
const catalog = require('./steam/achievements.json');
const { cloudPaths, INCLUDE, EXCLUDE } = require('./steam/cloud_paths.cjs');
const { resolveEdition, editionConfig } = require('./steam/edition.cjs');

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rov-steam-'));
try {
  assert.equal(resolveEdition({ ROV_BUILD_EDITION: 'steam' }), 'steam');
  assert.equal(resolveEdition({ ROV_BUILD_EDITION: 'internal' }), 'internal');
  assert.equal(editionConfig({ ROV_BUILD_EDITION: 'steam' }).showAchievements, true);
  assert.equal(editionConfig({ ROV_BUILD_EDITION: 'internal' }).showAchievements, false);

  // Requiring forge.config must not rewrite the tracked bake file (dirty worktree).
  const bakePath = path.join(__dirname, 'steam', 'build_edition.json');
  const beforeBake = fs.readFileSync(bakePath);
  const forge = require('./forge.config.cjs');
  assert.equal(fs.readFileSync(bakePath).equals(beforeBake), true);
  assert.equal(typeof forge.hooks.packageAfterCopy, 'function');
  assert.ok(forge.packagerConfig.name);
  assert.ok(INCLUDE.includes('preferences.json'));
  assert.ok(EXCLUDE.includes('numba-cache/**'));

  const paths = cloudPaths(root);
  assert.equal(paths.root, path.resolve(root));
  assert.ok(paths.mockState.endsWith(path.join('steam-mock', 'state.json')));

  const mock = createSteam(root, {
    env: { ROV_BUILD_EDITION: 'steam' },
    loadSteam: () => { throw Error('offline fixture'); },
    logger: { warn() {} },
  });
  const offline = mock.status();
  assert.equal(offline.available, false);
  assert.equal(offline.backend, 'mock');
  assert.equal(offline.edition, 'steam');
  assert.equal(mock.report('first_dive', 1), true);
  assert.throws(() => mock.report('../unknown', 1));
  assert.throws(() => mock.report('first_dive', -1));
  const saved = mock.readMock();
  assert.ok(saved.achievements.first_dive);
  assert.equal(saved.stats.STAT_FIRST_DIVE, 1);
  assert.ok(fs.existsSync(paths.mockState));

  assert.equal(mock.setPresence({ chapter: '第一章', level: '碼頭巡檢', language: 'zh-Hant' }), true);
  assert.equal(mock.readMock().presence.chapter, '第一章');
  assert.equal(mock.readMock().presence.level, '碼頭巡檢');

  const calls = [];
  const online = createSteam(root, {
    env: { ROV_BUILD_EDITION: 'steam', STEAM_APP_ID: '480' },
    loadSteam: () => ({
      init: () => ({
        achievement: { activate: (id) => { calls.push(id); return true; } },
        stats: {
          getInt: () => 0,
          setInt: () => true,
          store: () => true,
        },
        localplayer: {
          getName: () => 'Tester',
          setRichPresence: (key, value) => { calls.push(`${key}=${value}`); },
        },
        apps: { currentGameLanguage: () => 'english' },
        utils: { isSteamRunningOnSteamDeck: () => false },
      }),
      electronEnableSteamOverlay: () => {},
    }),
    logger: { warn() {} },
  });
  assert.equal(online.status().available, true);
  assert.equal(online.status().backend, 'steamworks');
  assert.equal(online.status().player, 'Tester');
  for (const item of catalog) assert.equal(online.report(item.event, 1), true);
  assert.equal(new Set(calls.filter((item) => item.startsWith('ACH_'))).size, catalog.length);
  assert.equal(online.setPresence({ chapter: 'Chapter 1', level: 'Pier' }), true);
  assert.ok(calls.includes('steam_display=#StatusFull'));
  assert.ok(calls.includes('chapter=Chapter 1'));

  const bridge = createBridge(root, () => { throw Error('bridge offline'); });
  assert.equal(bridge.status().backend, 'mock');
  assert.equal(bridge.event('zero_collision'), true);

  assert.ok(catalog.length >= 15 && catalog.length <= 25);
  const events = new Set(catalog.map((item) => item.event));
  assert.equal(events.size, catalog.length);
  for (const item of catalog) {
    assert.ok(/^ACH_[A-Z0-9_]+$/.test(item.api), item.api);
    assert.ok(item.name && !/BlueROV|Falcon|QY|深之蓝/i.test(item.name), item.name);
  }

  console.log(`Steam adapter: mock, ${catalog.length} achievements, presence and cloud paths passed`);
} finally {
  fs.rmSync(root, { recursive: true, force: true });
}
