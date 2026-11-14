// The pilot's control layout (which stick drives which axis): one default and one stored preference.
// The launch menu, the engineering drawer and the join handshake all read and write it here.

// Same value as the simulator's own default (qysim/engine.py) and the first entry of the drawer's list.
export const DEFAULT_CONTROL_LAYOUT = 'ROV_USA';
export const CONTROL_LAYOUTS = ['ROV_USA', 'ROV_JPN', 'ROV_CHN', 'UAV_USA', 'UAV_JPN', 'UAV_CHN'];
export const CONTROL_LAYOUT_KEY = 'rov.controlLayout.v1';

function defaultStorage() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

// The layout the pilot chose earlier, or null when nothing valid is stored.
export function storedControlLayout(storage = defaultStorage()) {
  try {
    const value = storage?.getItem(CONTROL_LAYOUT_KEY);
    return CONTROL_LAYOUTS.includes(value) ? value : null;
  } catch {
    return null;
  }
}

export function controlLayout(storage = defaultStorage()) {
  return storedControlLayout(storage) || DEFAULT_CONTROL_LAYOUT;
}

export function rememberControlLayout(value, storage = defaultStorage()) {
  if (!CONTROL_LAYOUTS.includes(value)) return false;
  try {
    storage?.setItem(CONTROL_LAYOUT_KEY, value);
  } catch {
    return false;
  }
  return true;
}
