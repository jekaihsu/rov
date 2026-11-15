// The pilot's control layout (which stick drives which axis): one default and one stored preference.
// The launch menu, the engineering drawer and the join handshake all read and write it here.

// Same value as the simulator's own default (qysim/engine.py) and the first entry of the drawer's list.
export const DEFAULT_CONTROL_LAYOUT = 'ROV_USA';
export const CONTROL_LAYOUTS = ['ROV_USA', 'ROV_JPN', 'ROV_CHN', 'UAV_USA', 'UAV_JPN', 'UAV_CHN'];
export const CONTROL_LAYOUT_KEY = 'rov.controlLayout.v1';
// Player-facing names; the values above are the simulator's operation-mode keys and never shown as such.
const STRINGS = {
  layouts: {
    ROV_USA: '標準配置（左桿俯仰／轉向，右桿前後）',
    ROV_JPN: '日式配置（左桿前後／轉向）',
    ROV_CHN: '中式配置（左桿前後，右桿轉向）',
    UAV_USA: '空拍機配置（左桿升降／轉向）',
    UAV_JPN: '空拍機日式配置',
    UAV_CHN: '雙桿配置（左桿前後／平移）',
  },
};

export function controlLayoutLabel(value) {
  return STRINGS.layouts[value] || STRINGS.layouts[DEFAULT_CONTROL_LAYOUT];
}

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
