// Fidelity profile: the single source of truth for "real" / "standard" / "assisted" behaviour.
// Every feature that exceeds real-vehicle capability registers an item here and defaults to off in `real`.
// The module owns presets, per-item values, persistence, URL overrides and change notification.
// It never touches physics or protocol; consumers read values and react to changes.
const STRINGS = {
  title: '擬真設定',
  presetReal: '真實',
  presetStandard: '標準',
  presetAssisted: '簡單',
  presetCustom: '自訂',
  assistLevel: '飛行輔助',
  assistLevelHelp: '真機推桿即推力；速度與定點輔助會主動煞停，伺服器支援時才生效。',
  assistManual: '手動（推桿即推力）',
  assistVelocity: '速度輔助',
  assistHold: '定點輔助',
  flightProfile: '飛行檔位',
  flightProfileHelp: '只影響輔助開啟時的速度上限與搖桿曲線。',
  profileCine: '電影',
  profileNormal: '標準',
  profileSport: '運動',
  videoDelayMs: '影像延遲',
  videoDelayMsHelp: '真機影像有延遲（預設 150 ms）；設為 0 為低延遲預測顯示。',
  cameraView: '預設視角',
  cameraViewHelp: '真機只有機載第一人稱；其他視角需先開啟第三人稱。',
  viewOnboard: '機載',
  viewChase: '追蹤',
  viewOrbit: '環繞',
  viewTop: '俯視',
  gimbal: '雲台穩定',
  gimbalHelp: '關閉時鏡頭與機身硬連結，畫面隨機身橫滾俯仰。',
  thirdPerson: '第三人稱視角',
  thirdPersonHelp: '訓練輔助：允許切換到追蹤、環繞與俯視。',
  hudDensity: 'HUD 密度',
  hudDensityHelp: '飛行畫面顯示的資訊量。',
  densityMinimal: '極簡',
  densityStandard: '標準',
  densityFull: '完整',
  hudStyle: 'HUD 樣式',
  hudStyleHelp: '自動：真實模式的機載畫面用影像疊字，其他情況用線條儀表。',
  hudStyleAuto: '自動',
  hudStyleLine: '線條儀表',
  hudStyleOsd: '影像疊字',
  unitMs: 'ms'
};
// Player-facing difficulty order (easy → hard). Internal keys stay stable for saves and URLs.
export const PRESET_NAMES = ['real', 'standard', 'assisted'];
export const DIFFICULTY_ORDER = ['assisted', 'standard', 'real'];
export const STORAGE_KEY = 'rov.fidelity.v1';
// Missing `standard` defaults fall back to `real` so existing registerFidelityItem calls stay valid.
function presetDefault(item, preset) {
  if (Object.prototype.hasOwnProperty.call(item.defaults || {}, preset)) return item.defaults[preset];
  if (preset === 'standard') return item.defaults?.real;
  return undefined;
}
const THIRD_PERSON_VIEWS = ['chase', 'orbit', 'top'];
const registry = new Map();
const stores = new Set();
let singleton = null;

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}
function flagFromUrl(params, name) {
  if (!params.has(name)) return undefined;
  return params.get(name) === '1' || params.get(name) === 'true';
}
function numberOption(item, value) {
  const number = Number(value);
  if (value === null || value === '' || typeof value === 'boolean' || !Number.isFinite(number)) return undefined;
  return clamp(number, item.min ?? -Infinity, item.max ?? Infinity);
}
function choiceOption(item, value) {
  const match = item.options.find(function sameValue(option) {
    return option.value === value || String(option.value) === String(value);
  });
  return match ? match.value : undefined;
}
// Returns a valid value for the item, or undefined when the input cannot be used.
export function normalizeFidelityValue(item, value) {
  if (value === undefined) return undefined;
  if (item.type === 'toggle') return typeof value === 'boolean' ? value : undefined;
  if (item.type === 'range') return numberOption(item, value);
  return choiceOption(item, value);
}
function defaultExceeds(item) {
  return function differsFromReal(value) {
    return item.exceedsReal && value !== item.defaults.real;
  };
}
// Registers one fidelity item. `strings` optionally supplies the label texts for the keys the item uses.
export function registerFidelityItem(definition, strings = {}) {
  const item = {type: 'choice', exceedsReal: false, presetNeutral: false, ...definition};
  if (!item.id || typeof item.id !== 'string') throw new Error('Fidelity item needs an id');
  if (registry.has(item.id)) throw new Error(`Fidelity item already registered: ${item.id}`);
  if (!['choice', 'toggle', 'range'].includes(item.type)) throw new Error(`Unknown fidelity type: ${item.type}`);
  if (item.type === 'choice' && !item.options?.length) throw new Error(`Fidelity item needs options: ${item.id}`);
  item.labelKey ||= item.id;
  item.exceeds ||= defaultExceeds(item);
  for (const preset of PRESET_NAMES) {
    const value = normalizeFidelityValue(item, presetDefault(item, preset));
    if (value === undefined) throw new Error(`Fidelity item ${item.id} needs a valid ${preset} default`);
  }
  // Resolve fallbacks into the frozen item so consumers can read defaults.standard directly.
  item.defaults = Object.freeze({
    real: normalizeFidelityValue(item, presetDefault(item, 'real')),
    standard: normalizeFidelityValue(item, presetDefault(item, 'standard')),
    assisted: normalizeFidelityValue(item, presetDefault(item, 'assisted')),
  });
  if (item.exceeds(item.defaults.real)) {
    throw new Error(`Fidelity item ${item.id} must not exceed the real vehicle in the real preset`);
  }
  Object.assign(STRINGS, strings);
  registry.set(item.id, Object.freeze(item));
  for (const refresh of stores) refresh([item.id]);
  return item;
}
export function fidelityItems() {
  return [...registry.values()];
}
export function fidelityText(key) {
  return STRINGS[key] ?? key;
}
function readStored(storage) {
  try {
    const data = JSON.parse(storage?.getItem(STORAGE_KEY) || 'null');
    if (!data || typeof data !== 'object') return {};
    return data;
  } catch {
    return {};
  }
}
// Creates an independent store. The app uses getFidelity(); tests inject storage, search and edition.
export function createFidelity({storage = null, search = '', edition = null} = {}) {
  const params = new URLSearchParams(search);
  const stored = readStored(storage);
  const urlPreset = PRESET_NAMES.includes(params.get('fidelity')) ? params.get('fidelity') : null;
  const storedBase = PRESET_NAMES.includes(stored.base) ? stored.base : null;
  const listeners = new Set();
  // `edition` remains in the API for desktop callers; both steam and training now default to real.
  // Easier presets are chosen on the new-game screen (or via ?fidelity= / settings).
  void edition;
  let base = urlPreset || storedBase || 'real';
  let overrides = {};
  let urlActive = true;
  if (!urlPreset && stored.overrides && typeof stored.overrides === 'object') overrides = {...stored.overrides};
  const dismissed = new Set();

  function urlValue(item) {
    if (!urlActive || dismissed.has(item.id) || !item.urlValue) return undefined;
    return normalizeFidelityValue(item, item.urlValue(params));
  }
  function storedValue(item) {
    const value = normalizeFidelityValue(item, overrides[item.id]);
    return value === undefined ? item.defaults[base] : value;
  }
  function valueOf(item) {
    const fromUrl = urlValue(item);
    return fromUrl === undefined ? storedValue(item) : fromUrl;
  }
  function get(id) {
    const item = registry.get(id);
    return item ? valueOf(item) : undefined;
  }
  function matches(name, read) {
    return fidelityItems().every(function sameAsPreset(item) {
      return item.presetNeutral || read(item) === item.defaults[name];
    });
  }
  function presetOf(read) {
    if (matches(base, read)) return base;
    const other = PRESET_NAMES.find(function candidate(name) {
      return name !== base && matches(name, read);
    });
    return other || 'custom';
  }
  function snapshot() {
    const values = {};
    for (const item of fidelityItems()) values[item.id] = valueOf(item);
    return {preset: presetOf(valueOf), base, values};
  }
  function notify(changed) {
    const current = snapshot();
    for (const listener of [...listeners]) listener(current, changed);
  }
  function persist() {
    try {
      storage?.setItem(STORAGE_KEY, JSON.stringify({version: 1, base, overrides}));
    } catch {
      // Private browsing or a full quota: the session keeps working without persistence.
    }
  }
  function tidy() {
    const settled = presetOf(storedValue);
    if (settled !== 'custom') base = settled;
    for (const item of fidelityItems()) {
      if (storedValue(item) === item.defaults[base]) delete overrides[item.id];
    }
  }
  function set(id, value) {
    const item = registry.get(id);
    if (!item) return false;
    const next = normalizeFidelityValue(item, value);
    if (next === undefined) return false;
    if (valueOf(item) === next) return true;
    dismissed.add(id);
    overrides[id] = next;
    tidy();
    persist();
    notify([id]);
    return true;
  }
  function setPreset(name) {
    if (!PRESET_NAMES.includes(name)) return false;
    base = name;
    overrides = {};
    urlActive = false;
    persist();
    notify(fidelityItems().map(function itemId(item) {
      return item.id;
    }));
    return true;
  }
  function subscribe(listener) {
    listeners.add(listener);
    return function unsubscribe() {
      listeners.delete(listener);
    };
  }
  function exceeds(id) {
    const item = registry.get(id);
    return !!item && !!item.exceeds(valueOf(item));
  }
  function fromUrl(id) {
    const item = registry.get(id);
    return !!item && urlValue(item) !== undefined;
  }
  function dispose() {
    stores.delete(notify);
    listeners.clear();
  }
  stores.add(notify);
  return {
    get preset() {
      return presetOf(valueOf);
    },
    get base() {
      return base;
    },
    get, set, setPreset, snapshot, subscribe, exceeds, fromUrl, dispose,
    items: fidelityItems
  };
}
// The shared store for the running page: localStorage, the page URL and the optional desktop edition field.
export function getFidelity() {
  if (singleton) return singleton;
  const host = globalThis.window;
  let storage = null;
  try {
    storage = host?.localStorage || null;
  } catch {
    storage = null;
  }
  singleton = createFidelity({
    storage,
    search: host?.location?.search || '',
    edition: host?.rovDesktop?.edition || null
  });
  return singleton;
}
export function isThirdPersonView(view) {
  return THIRD_PERSON_VIEWS.includes(view);
}
function videoDelayFromUrl(params) {
  if (params.get('presentation') === 'assisted') return 0;
  return params.has('videoDelayMs') ? params.get('videoDelayMs') : undefined;
}
function thirdPersonFromUrl(params) {
  const flag = flagFromUrl(params, 'thirdPerson');
  if (flag !== undefined) return flag;
  return isThirdPersonView(params.get('cam')) ? true : undefined;
}
function isAssistOn(value) {
  return value > 0;
}
function isBelowRealDelay(value) {
  return value < 150;
}
function isTrue(value) {
  return value === true;
}
function urlParam(name) {
  return function read(params) {
    return params.has(name) ? params.get(name) : undefined;
  };
}
function urlFlag(name) {
  return function read(params) {
    return flagFromUrl(params, name);
  };
}
registerFidelityItem({
  id: 'assistLevel', descriptionKey: 'assistLevelHelp', type: 'choice',
  options: [
    {value: 0, labelKey: 'assistManual'},
    {value: 1, labelKey: 'assistVelocity'},
    {value: 2, labelKey: 'assistHold'}
  ],
  // standard: 定點輔助關（推桿即推力）；assisted 仍開定點。
  defaults: {real: 0, standard: 0, assisted: 2}, exceedsReal: true, exceeds: isAssistOn
});
registerFidelityItem({
  id: 'flightProfile', descriptionKey: 'flightProfileHelp', type: 'choice',
  options: [
    {value: 'cine', labelKey: 'profileCine'},
    {value: 'normal', labelKey: 'profileNormal'},
    {value: 'sport', labelKey: 'profileSport'}
  ],
  defaults: {real: 'normal', assisted: 'normal'}, presetNeutral: true
});
registerFidelityItem({
  // Provisional generic latency from the research report, not a vehicle-specific measurement.
  // standard keeps real latency; assisted drops it for a snappier training feel.
  id: 'videoDelayMs', descriptionKey: 'videoDelayMsHelp', type: 'range', min: 0, max: 1000, step: 10,
  unitKey: 'unitMs', defaults: {real: 150, standard: 150, assisted: 0}, exceedsReal: true, exceeds: isBelowRealDelay,
  urlValue: videoDelayFromUrl
});
registerFidelityItem({
  id: 'cameraView', descriptionKey: 'cameraViewHelp', type: 'choice',
  options: [
    {value: 'onboard', labelKey: 'viewOnboard'},
    {value: 'chase', labelKey: 'viewChase'},
    {value: 'orbit', labelKey: 'viewOrbit'},
    {value: 'top', labelKey: 'viewTop'}
  ],
  defaults: {real: 'onboard', assisted: 'onboard'}, presetNeutral: true, urlValue: urlParam('cam')
});
registerFidelityItem({
  id: 'gimbal', descriptionKey: 'gimbalHelp', type: 'toggle',
  defaults: {real: false, assisted: true}, exceedsReal: true, exceeds: isTrue, urlValue: urlFlag('gimbal')
});
registerFidelityItem({
  id: 'thirdPerson', descriptionKey: 'thirdPersonHelp', type: 'toggle',
  defaults: {real: false, assisted: true}, exceedsReal: true, exceeds: isTrue, urlValue: thirdPersonFromUrl
});
registerFidelityItem({
  id: 'hudDensity', descriptionKey: 'hudDensityHelp', type: 'choice',
  options: [
    {value: 0, labelKey: 'densityMinimal'},
    {value: 1, labelKey: 'densityStandard'},
    {value: 2, labelKey: 'densityFull'}
  ],
  defaults: {real: 1, assisted: 1}, presetNeutral: true
});
registerFidelityItem({
  // Presentation only: both styles show the same delayed read-outs, so neither exceeds the real vehicle.
  id: 'hudStyle', descriptionKey: 'hudStyleHelp', type: 'choice',
  options: [
    {value: 'auto', labelKey: 'hudStyleAuto'},
    {value: 'line', labelKey: 'hudStyleLine'},
    {value: 'osd', labelKey: 'hudStyleOsd'}
  ],
  defaults: {real: 'auto', assisted: 'auto'}, presetNeutral: true, urlValue: urlParam('hudStyle')
});
