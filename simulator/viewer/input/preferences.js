// Shared, versioned binding state for launch navigation, the editor and the flight input sampler.
import { BINDINGS_VERSION, editablePadBindings } from './bindings.js';

function record(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

async function load() {
  let stored = {};
  try {
    stored = record(JSON.parse(globalThis.localStorage?.getItem('rov.input.v1') || '{}'));
  } catch {}
  try {
    const desktop = record(await globalThis.rovDesktop?.readInput?.());
    if (Object.keys(desktop).length) stored = desktop;
  } catch {}
  return {
    ...stored, custom: record(stored.custom), channels: record(stored.channels), keys: record(stored.keys),
    bindings: editablePadBindings(stored.bindings, stored.bindingsVersion), bindingsVersion: BINDINGS_VERSION,
  };
}
export const inputPreferences = await load();

export function saveInputPreferences() {
  try {
    localStorage.setItem('rov.input.v1', JSON.stringify(inputPreferences));
  } catch {}
  globalThis.rovDesktop?.rememberInput?.(inputPreferences);
}
