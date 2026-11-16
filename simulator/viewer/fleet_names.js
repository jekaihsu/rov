// Player-facing names of the YX fleet and named sites (docs/design/game-plan.md §10).
// The single source of truth for every name a player reads: hangar, briefing, HUD, multiplayer list, collection,
// results. Internal model ids, saves, protocol fields and SDK behaviour keep their original keys; only the
// displayed text changes here. The Python counterpart is simulator/qysim/fleet_names.py; keep both in step.

export const STRINGS = {
  models: {
    x1: {
      name: 'YX Model R',
      role: '入門觀測型',
      tagline: '輕巧好上手，第一台陪你看清水下的觀測機。',
    },
    bluerov2_heavy: {
      name: 'YX Model O',
      role: '重載觀測型',
      tagline: '推力充足、掛載空間大，強流與長時間觀測的主力。',
    },
    falcon: {
      name: 'YX Model V',
      role: '輕作業型',
      tagline: '搭載機械臂，能執行回收與佈放等輕作業。',
    },
  },
  fallbackName: 'ROV',
  blockLabel: 'Block',
  separator: ' · ',
  sites: {
    korean_castle: '碧海號',
  },
};

/** Ids of the fleet in display order. */
export const FLEET_IDS = Object.freeze(Object.keys(STRINGS.models));

function entryFor(modelId) {
  return Object.hasOwn(STRINGS.models, modelId || '') ? STRINGS.models[modelId] : null;
}

/** Display name for a model id ("YX Model R"); unknown ids fall back to the id itself, or "ROV" when empty. */
export function vehicleName(modelId) {
  return entryFor(modelId)?.name || modelId || STRINGS.fallbackName;
}

/** Short role line ("入門觀測型"), or an empty string for an unknown id. */
export function vehicleRole(modelId) {
  return entryFor(modelId)?.role || '';
}

/** One-sentence tagline, or an empty string for an unknown id. */
export function vehicleTagline(modelId) {
  return entryFor(modelId)?.tagline || '';
}

/** Role and tagline joined for a hangar detail line. */
export function vehicleDetail(modelId) {
  return [vehicleRole(modelId), vehicleTagline(modelId)].filter(Boolean).join(STRINGS.separator);
}

/**
 * Block (iteration) number of a model for a career save (viewer/career/save.js): equipment bought at the YX
 * equipment department raises it (career/rules.js keeps save.vehicles up to date). No save, or a model the
 * save does not list, is Block 1.
 */
export function blockFor(modelId, save) {
  const block = Number(save?.vehicles?.[modelId]?.block);
  return Number.isFinite(block) && block >= 1 ? Math.floor(block) : 1;
}

/** Name with its Block number, e.g. "YX Model R · Block 1". */
export function vehicleTitle(modelId, save) {
  const block = `${STRINGS.blockLabel} ${blockFor(modelId, save)}`;
  return [vehicleName(modelId), block].join(STRINGS.separator);
}

/** Player-facing name of a named site by scenario key, or null when the site has no proper name. */
export function siteName(scenarioKey) {
  return Object.hasOwn(STRINGS.sites, scenarioKey || '') ? STRINGS.sites[scenarioKey] : null;
}
