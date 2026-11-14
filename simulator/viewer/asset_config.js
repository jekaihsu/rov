// Visual asset set selection. `?assets=generic` swaps vehicle visuals for the original Steam-edition models;
// anything else (the default) keeps the internal training models. Physics ids, SDK semantics and the
// fidelity setting are untouched: this only changes which GLB is drawn for a vehicle id.

export const STRINGS = {
  observationName: '觀測型 ROV',
  observationDetail: '六推進器 · 開放框架',
};

// Alternate visuals per physics vehicle id. LOD URLs are ordered from nearest to farthest.
export const GENERIC_VEHICLES = {
  x1: {
    lods: ['models/observation_rov.glb', 'models/observation_rov_lod1.glb', 'models/observation_rov_lod2.glb'],
    name: STRINGS.observationName,
    detail: STRINGS.observationDetail,
  },
};

function readAssetQuery() {
  try {
    return new URLSearchParams(globalThis.location?.search || '').get('assets');
  } catch {
    return null;
  }
}

/** 'generic' when the original Steam-edition visuals are requested, otherwise 'training'. */
export function assetSet(override) {
  const value = override ?? readAssetQuery();
  return value === 'generic' ? 'generic' : 'training';
}

/** The alternate visual for a vehicle id in the given asset set, or null to keep the definition's model. */
export function genericVehicle(id, set = assetSet()) {
  if (set !== 'generic') {
    return null;
  }
  return GENERIC_VEHICLES[id] || null;
}

/** Model URL for a vehicle id at a level of detail (0 nearest), or null for the training model. */
export function genericVehicleUrl(id, lod = 0, set = assetSet()) {
  const entry = genericVehicle(id, set);
  if (!entry) {
    return null;
  }
  const index = Math.max(0, Math.min(entry.lods.length - 1, lod));
  return entry.lods[index];
}

/** Rename menu entries in place when the generic set swaps their visual (never show the training name). */
export function applyGenericLabels(models, set = assetSet()) {
  for (const [id, entry] of Object.entries(models)) {
    const generic = genericVehicle(id, set);
    if (generic) {
      entry.name = generic.name;
      entry.detail = generic.detail;
    }
  }
  return models;
}
