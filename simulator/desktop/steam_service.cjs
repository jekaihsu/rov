// Steamworks boundary for the Electron main process.
// With a valid App ID and a running Steam client, uses steamworks.js (MIT).
// Otherwise writes a local mock JSON under userData/steam-mock so gameplay and tests keep working.
const fs = require('node:fs');
const path = require('node:path');
const catalog = require('./steam/achievements.json');
const { cloudPaths } = require('./steam/cloud_paths.cjs');
const { resolveEdition } = require('./steam/edition.cjs');

const EVENT_BY_ID = new Map(catalog.map(function entry(item) {
  return [item.event, item];
}));

function readAppId(env, execPath) {
  let id = env.STEAM_APP_ID || '';
  if (!id) {
    try {
      const file = path.join(path.dirname(execPath), 'steam_appid.txt');
      if (fs.existsSync(file)) id = fs.readFileSync(file, 'utf8').trim();
    } catch {
      // Missing file is the common development case.
    }
  }
  if (!id) return null;
  if (!/^[1-9][0-9]*$/.test(id)) throw Error('Invalid STEAM_APP_ID');
  return Number(id);
}

function emptyMock() {
  return { achievements: {}, stats: {}, presence: null, updatedAt: null };
}

function loadMock(file) {
  try {
    const raw = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (!raw || typeof raw !== 'object') return emptyMock();
    return {
      achievements: raw.achievements && typeof raw.achievements === 'object' ? raw.achievements : {},
      stats: raw.stats && typeof raw.stats === 'object' ? raw.stats : {},
      presence: raw.presence && typeof raw.presence === 'object' ? raw.presence : null,
      updatedAt: typeof raw.updatedAt === 'string' ? raw.updatedAt : null,
    };
  } catch {
    return emptyMock();
  }
}

function saveMock(file, state) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const next = { ...state, updatedAt: new Date().toISOString() };
  const temp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temp, `${JSON.stringify(next, null, 2)}\n`, 'utf8');
  fs.renameSync(temp, file);
  return next;
}

function createSteam(userData, options = {}) {
  const env = options.env || process.env;
  const logger = options.logger || console;
  const loadSteam = options.loadSteam || (() => require('steamworks.js'));
  const execPath = options.execPath || process.execPath;
  const edition = resolveEdition(env);
  const paths = cloudPaths(userData);
  const mockFile = paths.mockState;
  let mock = loadMock(mockFile);
  let client = null;
  let backend = 'mock';
  let error = null;

  try {
    const appId = readAppId(env, execPath);
    if (appId) {
      const steam = loadSteam();
      client = steam.init(appId);
      if (typeof steam.electronEnableSteamOverlay === 'function') {
        steam.electronEnableSteamOverlay();
      }
      backend = 'steamworks';
    } else {
      error = 'No STEAM_APP_ID; using local mock backend';
    }
  } catch (failure) {
    client = null;
    backend = 'mock';
    error = failure.message || String(failure);
    logger.warn('Steam unavailable; offline mock remains available:', error);
  }

  function status() {
    return {
      available: backend === 'steamworks',
      backend,
      edition,
      player: client?.localplayer?.getName?.() ?? null,
      language: client?.apps?.currentGameLanguage?.() ?? null,
      cloudPath: userData,
      cloud: paths,
      deck: client?.utils?.isSteamRunningOnSteamDeck?.() ?? false,
      overlayActive: null,
      overlayDetection: 'unsupported-by-steamworks.js',
      error,
      mockPath: mockFile,
      earned: Object.keys(mock.achievements),
      presence: mock.presence,
    };
  }

  function report(event, value = 1) {
    const entry = EVENT_BY_ID.get(event);
    if (!entry || !Number.isSafeInteger(value) || value < 0 || value > 2147483647) {
      throw Error('Invalid Steam event');
    }
    const statName = `STAT_${event.toUpperCase()}`;
    if (client) {
      const previous = client.stats.getInt(statName) ?? 0;
      const saved = client.stats.setInt(statName, Math.max(previous, value));
      const unlocked = client.achievement.activate(entry.api);
      return saved && unlocked && client.stats.store();
    }
    const previous = Number(mock.stats[statName]) || 0;
    mock.stats[statName] = Math.max(previous, value);
    if (!mock.achievements[event]) {
      mock.achievements[event] = { api: entry.api, unlockedAt: new Date().toISOString(), value };
    } else {
      mock.achievements[event].value = Math.max(mock.achievements[event].value || 0, value);
    }
    mock = saveMock(mockFile, mock);
    return true;
  }

  function setPresence(payload = {}) {
    const chapter = typeof payload.chapter === 'string' ? payload.chapter.slice(0, 128) : '';
    const level = typeof payload.level === 'string' ? payload.level.slice(0, 128) : '';
    const language = typeof payload.language === 'string' ? payload.language.slice(0, 16) : '';
    const presence = { chapter, level, language, updatedAt: new Date().toISOString() };
    if (client?.localplayer?.setRichPresence) {
      client.localplayer.setRichPresence('steam_display', '#StatusFull');
      client.localplayer.setRichPresence('chapter', chapter);
      client.localplayer.setRichPresence('level', level);
      return true;
    }
    mock.presence = presence;
    mock = saveMock(mockFile, mock);
    return true;
  }

  function readMock() {
    mock = loadMock(mockFile);
    return mock;
  }

  return { status, report, setPresence, readMock, edition, paths };
}

module.exports = { createSteam, EVENT_BY_ID };
