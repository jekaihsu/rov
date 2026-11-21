// Catalogue of every player-facing save key: schema version, defaults, migrate and normalize.
// Callers that own domain logic (career, fidelity, display) keep their richer normalisers and
// pass them here; this module is the inventory the docs and soak tests refer to.

import { createRecordStore, createScalarStore } from './store.js';

function isObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function flags(source, names) {
  const result = {};
  for (const name of names) result[name] = !!source?.[name];
  return result;
}

function finite(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function clamp(value, low, high) {
  return Math.min(high, Math.max(low, value));
}

const ONBOARDING_STEPS = ['unlock', 'move', 'depth', 'light', 'photo', 'objectives', 'pause'];
const ONBOARDING_MOVES = ['surge', 'yaw', 'heave'];
const ONBOARDING_TIPS = ['tether', 'dvl', 'visibility'];
const AUDIO_DEFAULTS = {
  master: 0.65,
  vehicle: 0.7,
  environment: 0.5,
  ui: 0.55,
  warning: 0.65,
  music: 0.5,
  voice: 0.8,
  mute: false,
};
const DISPLAY_DEFAULTS = {
  language: 'zh-Hant',
  brightness: 1,
  uiScale: 1,
  colorBlind: 'off',
  units: 'metric',
  fpsCap: 0,
};
const LANGUAGES = ['zh-Hant', 'en', 'zh-Hans', 'ja'];
const COLOR_BLIND = ['off', 'deuteranopia', 'protanopia', 'tritanopia'];
const FPS_CAPS = [0, 30, 60, 120];
const INTERFACE_DEFAULTS = { pip: false, intro: true, sticks: true, fog: true, labels: true };
const CONTROL_LAYOUTS = ['ROV_USA', 'ROV_JPN', 'ROV_CHN', 'UAV_USA', 'UAV_JPN', 'UAV_CHN'];
const QUALITY_MODES = ['auto', 'performance', 'medium', 'high'];
const MODEL_IDS = ['x1', 'bluerov2_heavy', 'falcon'];
const FIDELITY_BASES = ['real', 'assisted'];

export const campaignStore = createRecordStore({
  key: 'rov.campaign.v1',
  version: 1,
  defaults() {
    return { completed: [], rewards: [], results: [], checkpoint: null };
  },
  migrate(record, fromVersion) {
    if (fromVersion === 0) {
      return {
        completed: Array.isArray(record.completed) ? record.completed : [],
        rewards: Array.isArray(record.rewards) ? record.rewards : [],
        results: Array.isArray(record.results) ? record.results : [],
        checkpoint: record.checkpoint ?? null,
      };
    }
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    return {
      completed: Array.isArray(record.completed)
        ? record.completed.filter((id) => typeof id === 'string').slice(0, 64)
        : [],
      rewards: Array.isArray(record.rewards) ? record.rewards.slice(0, 64) : [],
      results: Array.isArray(record.results) ? record.results.slice(0, 128) : [],
      checkpoint: record.checkpoint == null || isObject(record.checkpoint) ? record.checkpoint : null,
    };
  },
});

export const resultsStore = createRecordStore({
  key: 'rov.results.v1',
  version: 1,
  maxBytes: 256 * 1024,
  defaults() {
    // Flat map of recordKey → {best, medal, at}; `version` is added by the store.
    return {};
  },
  migrate(record) {
    // Pre-version flat maps and v1 both keep the same shape.
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    const records = {};
    for (const [key, entry] of Object.entries(record)) {
      if (key === 'version') continue;
      if (typeof key !== 'string' || key.length > 96 || !isObject(entry)) continue;
      const best = finite(entry.best, NaN);
      if (!Number.isFinite(best)) continue;
      records[key] = {
        best: clamp(best, 0, 100),
        medal: ['gold', 'silver', 'bronze', 'none'].includes(entry.medal) ? entry.medal : 'none',
        at: finite(entry.at, 0),
      };
      if (Object.keys(records).length >= 500) break;
    }
    return records;
  },
});

export const fidelityStore = createRecordStore({
  key: 'rov.fidelity.v1',
  version: 1,
  defaults() {
    return { base: 'real', overrides: {} };
  },
  migrate(record, fromVersion) {
    if (fromVersion === 0) {
      return {
        base: FIDELITY_BASES.includes(record.base) ? record.base : 'real',
        overrides: isObject(record.overrides) ? record.overrides : {},
      };
    }
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    return {
      base: FIDELITY_BASES.includes(record.base) ? record.base : 'real',
      overrides: isObject(record.overrides) ? record.overrides : {},
    };
  },
});

export const displayStore = createRecordStore({
  key: 'rov.display.v1',
  version: 1,
  defaults() {
    return { ...DISPLAY_DEFAULTS };
  },
  migrate(record) {
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    const value = { ...DISPLAY_DEFAULTS };
    if (LANGUAGES.includes(record.language)) value.language = record.language;
    if (Number.isFinite(record.brightness)) value.brightness = clamp(record.brightness, 0.7, 1.4);
    if (Number.isFinite(record.uiScale)) value.uiScale = clamp(record.uiScale, 0.85, 1.3);
    if (COLOR_BLIND.includes(record.colorBlind)) value.colorBlind = record.colorBlind;
    if (['metric', 'imperial'].includes(record.units)) value.units = record.units;
    if (FPS_CAPS.includes(record.fpsCap)) value.fpsCap = record.fpsCap;
    return value;
  },
});

export const audioStore = createRecordStore({
  key: 'rov.audio',
  version: 1,
  defaults() {
    return { ...AUDIO_DEFAULTS };
  },
  migrate(record, fromVersion) {
    if (fromVersion === 0) return { ...AUDIO_DEFAULTS, ...record };
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    const value = { ...AUDIO_DEFAULTS };
    for (const key of Object.keys(AUDIO_DEFAULTS)) {
      if (key === 'mute') {
        if (typeof record.mute === 'boolean') value.mute = record.mute;
        continue;
      }
      if (typeof record[key] === 'number' && Number.isFinite(record[key])) {
        value[key] = clamp(record[key], 0, 1);
      }
    }
    return value;
  },
});

export const onboardingStore = createRecordStore({
  key: 'rov.onboarding.v1',
  version: 1,
  defaults() {
    return {
      enabled: true,
      steps: flags({}, ONBOARDING_STEPS),
      moves: flags({}, ONBOARDING_MOVES),
      tips: flags({}, ONBOARDING_TIPS),
    };
  },
  migrate(record) {
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    return {
      enabled: record.enabled !== false,
      steps: flags(record.steps, ONBOARDING_STEPS),
      moves: flags(record.moves, ONBOARDING_MOVES),
      tips: flags(record.tips, ONBOARDING_TIPS),
    };
  },
});

export const achievementsStore = createRecordStore({
  key: 'rov.achievements.v1',
  version: 1,
  defaults() {
    return { earned: [], categories: [] };
  },
  migrate(record) {
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    const strings = (list) => Array.isArray(list)
      ? [...new Set(list.filter((item) => typeof item === 'string' && item.length <= 64))].slice(0, 128)
      : [];
    return { earned: strings(record.earned), categories: strings(record.categories) };
  },
});

export const coldOpenStore = createRecordStore({
  key: 'rov.coldOpen.v1',
  version: 1,
  defaults() {
    return { seen: false, enabled: true };
  },
  migrate(record) {
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    return { seen: !!record.seen, enabled: record.enabled !== false };
  },
});

export const objectiveCardStore = createRecordStore({
  key: 'rov.objectiveCard.v1',
  version: 1,
  defaults() {
    return { dives: 0, guideHidden: false, collapsed: false };
  },
  migrate(record) {
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    return {
      dives: Math.max(0, Math.round(finite(record.dives))),
      guideHidden: !!record.guideHidden,
      collapsed: !!record.collapsed,
    };
  },
});

export const qualityLearnedStore = createRecordStore({
  key: 'rov.quality.learned.v1',
  version: 1,
  defaults() {
    return { renderer: '', ratio: 1, effectsSuppressed: false };
  },
  migrate(record) {
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    if (typeof record.renderer !== 'string' || !Number.isFinite(record.ratio)) return null;
    return {
      renderer: record.renderer.slice(0, 200),
      ratio: clamp(record.ratio, 0.3, 2),
      effectsSuppressed: !!record.effectsSuppressed,
    };
  },
});

export const menuLastStore = createRecordStore({
  key: 'rov.menu.last.v1',
  version: 1,
  defaults() {
    return { model: '', mission: '', scenario: '', chapter: '', sticker: '', room: '' };
  },
  migrate(record) {
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    const text = (value) => (typeof value === 'string' ? value.slice(0, 64) : '');
    return {
      model: text(record.model),
      mission: text(record.mission),
      scenario: text(record.scenario),
      chapter: text(record.chapter),
      sticker: text(record.sticker),
      room: text(record.room),
    };
  },
});

export const menuSettingsStore = createRecordStore({
  key: 'rov.menuSettings',
  version: 1,
  defaults() {
    return { ...INTERFACE_DEFAULTS };
  },
  migrate(record, fromVersion) {
    if (fromVersion === 0) return { ...INTERFACE_DEFAULTS, ...record };
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    const value = { ...INTERFACE_DEFAULTS };
    for (const key of Object.keys(INTERFACE_DEFAULTS)) {
      if (typeof record[key] === 'boolean') value[key] = record[key];
    }
    return value;
  },
});

export const inputStore = createRecordStore({
  key: 'rov.input.v1',
  version: 1,
  maxBytes: 262144,
  defaults() {
    return { bindingsVersion: 2, bindings: {}, channels: {}, custom: {} };
  },
  migrate(record, fromVersion) {
    if (fromVersion === 0) {
      return {
        bindingsVersion: finite(record.bindingsVersion, 2),
        bindings: isObject(record.bindings) ? record.bindings : {},
        channels: isObject(record.channels) ? record.channels : {},
        custom: isObject(record.custom) ? record.custom : {},
        keys: isObject(record.keys) ? record.keys : undefined,
        inner: record.inner,
        outer: record.outer,
        strength: record.strength,
      };
    }
    return record;
  },
  normalize(record) {
    if (!isObject(record)) return null;
    const value = {
      bindingsVersion: Math.max(0, Math.round(finite(record.bindingsVersion, 2))),
      bindings: isObject(record.bindings) ? record.bindings : {},
      channels: isObject(record.channels) ? record.channels : {},
      custom: isObject(record.custom) ? record.custom : {},
    };
    if (isObject(record.keys)) value.keys = record.keys;
    for (const key of ['inner', 'outer', 'strength']) {
      if (Number.isFinite(record[key])) value[key] = record[key];
    }
    return value;
  },
});

export const careerStoreMeta = {
  key: 'rov.career.v1',
  version: 1,
  note: 'Owned by career/save.js (CAREER_VERSION); uses the same corrupt-backup helper.',
};

export const scalarStores = {
  playerName: createScalarStore({
    key: 'rov.playerName',
    version: 1,
    defaults: () => '操作員',
    validate: (value) => value.length <= 64,
  }),
  vehicle: createScalarStore({
    key: 'rov.vehicle',
    version: 1,
    defaults: () => 'x1',
    allowed: MODEL_IDS,
  }),
  quality: createScalarStore({
    key: 'rov.quality',
    version: 1,
    defaults: () => 'auto',
    allowed: QUALITY_MODES,
  }),
  mission: createScalarStore({
    key: 'rov.mission',
    version: 1,
    defaults: () => 'campaign',
    validate: (value) => value.length <= 64,
  }),
  sticker: createScalarStore({
    key: 'rov.sticker',
    version: 1,
    defaults: () => 'none',
    validate: (value) => value.length <= 64,
  }),
  operatorVisible: createScalarStore({
    key: 'rov.operatorVisible',
    version: 1,
    defaults: () => 'false',
    allowed: ['true', 'false'],
  }),
  hudDrawer: createScalarStore({
    key: 'rov.hud.drawer',
    version: 1,
    defaults: () => 'false',
    allowed: ['true', 'false'],
  }),
  pilotGuide: createScalarStore({
    key: 'rov.pilotGuide.dismissed.v1',
    version: 1,
    defaults: () => '0',
    allowed: ['0', '1'],
  }),
  controlLayout: createScalarStore({
    key: 'rov.controlLayout.v1',
    version: 1,
    defaults: () => 'ROV_USA',
    allowed: CONTROL_LAYOUTS,
  }),
};

export const recordStores = {
  campaign: campaignStore,
  results: resultsStore,
  fidelity: fidelityStore,
  display: displayStore,
  audio: audioStore,
  onboarding: onboardingStore,
  achievements: achievementsStore,
  coldOpen: coldOpenStore,
  objectiveCard: objectiveCardStore,
  qualityLearned: qualityLearnedStore,
  menuLast: menuLastStore,
  menuSettings: menuSettingsStore,
  input: inputStore,
};

/** Flat list used by docs, desktop sync and tests. */
export function allSaveEntries() {
  const entries = [
    {
      key: careerStoreMeta.key,
      version: careerStoreMeta.version,
      kind: 'record',
      owner: 'career/save.js',
      writeWhen: 'settle / purchase / logbook / abandoned dive / exam stash',
      onCorrupt: 'normalizeSave clamps; unreadable → defaultSave + legacy migrate; backup via save_store helper',
      desktopFile: 'saves/rov.career.v1.json (+ collection career-save mirror)',
    },
  ];
  for (const store of Object.values(recordStores)) {
    entries.push({
      key: store.key,
      version: store.version,
      kind: 'record',
      owner: 'saves/registry.js',
      writeWhen: 'see docs/design/saves.md',
      onCorrupt: 'defaults + backup to <key>.corrupt and userData/saves/corrupt/',
      desktopFile: `saves/${store.key}.json`,
    });
  }
  for (const store of Object.values(scalarStores)) {
    entries.push({
      key: store.key,
      version: store.version,
      kind: 'scalar',
      owner: 'saves/registry.js',
      writeWhen: 'see docs/design/saves.md',
      onCorrupt: 'defaults + backup',
      desktopFile: `saves/${store.key}.json`,
    });
  }
  entries.push({
    key: 'collection/index.json',
    version: 1,
    kind: 'file',
    owner: 'desktop/collection_store.cjs / viewer/collection_store.js',
    writeWhen: 'photo / result / cover / import',
    onCorrupt: 'reject import; ENOENT → empty index; atomic tmp+rename',
    desktopFile: 'collection/**',
  });
  entries.push({
    key: 'preferences.json',
    version: 1,
    kind: 'file',
    owner: 'desktop/main.cjs',
    writeWhen: 'model / quality / input IPC',
    onCorrupt: 'defaults; input size guard 262144',
    desktopFile: 'preferences.json',
  });
  entries.push({
    key: 'window.json',
    version: 1,
    kind: 'file',
    owner: 'desktop/window_settings.cjs',
    writeWhen: 'display IPC / Alt+Enter',
    onCorrupt: 'Deck fullscreen fallback / work-area window',
    desktopFile: 'window.json',
  });
  return entries;
}
