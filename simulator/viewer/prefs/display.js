// Player display preferences that do not change what the simulator does: language, brightness, interface and
// text scale, colour-blind warning colours, units on the game HUD and menus, and a frame-rate cap. One store
// (localStorage rov.display.v1) shared by the launch menu and the game; applied as attributes and CSS variables
// on <html> (play/play.css, menu.css, hud styles read them). Camera field of view and motion comfort are
// fidelity items instead (prefs/camera_items.js) because the camera rig reads the fidelity store.
// The instrument OSD keeps metric units: it mirrors the real vehicle's overlay.

const STRINGS = {
  languages: { 'zh-Hant': '繁體中文', en: 'English', 'zh-Hans': '简体中文', ja: '日本語' },
};

export const DISPLAY_KEY = 'rov.display.v1';
// Languages offered in settings. T09 adds entries here and the string tables behind them.
export const LANGUAGES = [
  { value: 'zh-Hant', label: STRINGS.languages['zh-Hant'], htmlLang: 'zh-Hant' },
  { value: 'en', label: STRINGS.languages['en'], htmlLang: 'en' },
  { value: 'zh-Hans', label: STRINGS.languages['zh-Hans'], htmlLang: 'zh-Hans' },
  { value: 'ja', label: STRINGS.languages['ja'], htmlLang: 'ja' },
];
export const DISPLAY_DEFAULTS = Object.freeze({
  language: 'zh-Hant',
  brightness: 1,
  uiScale: 1,
  colorBlind: 'off',
  units: 'metric',
  fpsCap: 0,
});
export const LIMITS = {
  brightness: [0.7, 1.4],
  uiScale: [0.85, 1.3],
};
export const COLOR_BLIND_MODES = ['off', 'deuteranopia', 'protanopia', 'tritanopia'];
export const FPS_CAPS = [0, 30, 60, 120];
const FEET = 3.28084;

function clamp(value, [low, high]) {
  return Math.min(high, Math.max(low, value));
}

// Valid preferences from anything stored or passed in; unknown or broken values fall back to the defaults.
export function normaliseDisplay(input = {}) {
  const value = { ...DISPLAY_DEFAULTS };
  if (LANGUAGES.some(function known(entry) {
    return entry.value === input.language;
  })) value.language = input.language;
  if (Number.isFinite(input.brightness)) value.brightness = clamp(input.brightness, LIMITS.brightness);
  if (Number.isFinite(input.uiScale)) value.uiScale = clamp(input.uiScale, LIMITS.uiScale);
  if (COLOR_BLIND_MODES.includes(input.colorBlind)) value.colorBlind = input.colorBlind;
  if (['metric', 'imperial'].includes(input.units)) value.units = input.units;
  if (FPS_CAPS.includes(input.fpsCap)) value.fpsCap = input.fpsCap;
  return value;
}

export function createDisplayPrefs({ storage = globalThis.localStorage } = {}) {
  let values;
  // The language is stored only once the player picks one; until then the Steam or browser language
  // decides (i18n/index.js). Saving the default with another preference would pin Traditional Chinese.
  let languageChosen = false;
  try {
    const stored = JSON.parse(storage?.getItem(DISPLAY_KEY) || '{}');
    values = normaliseDisplay(stored);
    languageChosen = values.language === stored?.language;
  } catch {
    values = normaliseDisplay();
  }
  const listeners = new Set();
  function set(id, value) {
    values = normaliseDisplay({ ...values, [id]: value });
    if (id === 'language') languageChosen = true;
    const saved = { ...values };
    if (!languageChosen) delete saved.language;
    try {
      storage?.setItem(DISPLAY_KEY, JSON.stringify(saved));
    } catch {
      // Storage may be unavailable; the choice still applies to this page.
    }
    for (const listener of listeners) listener(values, id);
  }
  return {
    get(id) {
      return values[id];
    },
    get values() {
      return { ...values };
    },
    set,
    subscribe(listener) {
      listeners.add(listener);
      return function unsubscribe() {
        listeners.delete(listener);
      };
    },
  };
}

let shared = null;

export function getDisplayPrefs() {
  shared ||= createDisplayPrefs();
  return shared;
}

// Lengths on the game HUD and in menus: metres, or feet in imperial.
export function lengthIn(metres, units = getDisplayPrefs().get('units')) {
  return units === 'imperial' ? metres * FEET : metres;
}

export function lengthUnit(units = getDisplayPrefs().get('units')) {
  return units === 'imperial' ? 'ft' : 'm';
}

// Frame-rate cap: true when this animation frame should be skipped. A quarter frame of slack keeps a 60 cap at
// 60 on a 60 Hz display instead of dropping every other frame.
export function createFrameGate(getCap = function cap() {
  return getDisplayPrefs().get('fpsCap');
}) {
  let last = -Infinity;
  return function skip(now) {
    const cap = getCap();
    if (!cap) {
      last = now;
      return false;
    }
    const interval = 1000 / cap;
    if (now - last < interval * 0.75) return true;
    last = now;
    return false;
  };
}

function apply(values, root, changed) {
  const language = LANGUAGES.find(function byValue(entry) {
    return entry.value === values.language;
  });
  root.lang = language?.htmlLang || root.lang;
  root.style.setProperty('--rov-brightness', String(values.brightness));
  root.style.setProperty('--rov-ui-scale', String(values.uiScale));
  root.dataset.colorBlind = values.colorBlind;
  root.dataset.units = values.units;
  document.dispatchEvent(new CustomEvent('rov-display-change', { detail: { ...values, changed } }));
}

// Applies the stored preferences to the page now and whenever they change.
export function installDisplayPrefs(root = document.documentElement) {
  const prefs = getDisplayPrefs();
  apply(prefs.values, root);
  prefs.subscribe(function changed(values, id) {
    apply(values, root, id);
  });
  return prefs;
}
