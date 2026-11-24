// The 顯示 settings tab shared by the launch menu and the pause menu: language, display mode and resolution
// (desktop shell only; a browser offers its own full screen), brightness, interface and text scale, frame-rate
// cap, colour-blind warning colours, units, external camera field of view, motion comfort and pad vibration
// strength. Display values live in prefs/display.js, camera values in the fidelity store (prefs/camera_items.js);
// every control writes through immediately and nothing here touches the simulation.
import { mountPreferenceRows } from '../fidelity_panel.js';
import '../prefs/accessibility.js';
import { inputPreferences, saveInputPreferences } from '../input/preferences.js';
import { getFidelity } from '../fidelity.js';
import { EXTERNAL_FOV_ITEM, MOTION_COMFORT_ITEM } from '../prefs/camera_items.js';
import { COLOR_BLIND_MODES, FPS_CAPS, LANGUAGES, LIMITS, getDisplayPrefs } from '../prefs/display.js';
import { element, field, mountToggles } from './settings.js';

import { getLanguage, localize } from '../i18n/index.js';

const STRINGS = localize('menu.display_settings', {
  language: '語言',
  languageHelp: '語言切換後，尚未更新的畫面會在返回主選單後生效。',
  monitor: '顯示器',
  window: '顯示模式',
  modes: { windowed: '視窗', borderless: '無邊框視窗', fullscreen: '全螢幕' },
  resolution: '解析度',
  apply: '套用顯示設定',
  applied: '已套用。',
  failed: '無法套用：{reason}',
  browserFullscreen: ['全螢幕', '瀏覽器版以瀏覽器的全螢幕顯示；解析度跟隨螢幕。'],
  brightness: '亮度',
  brightnessHelp: '只調整水下畫面，不影響儀表文字。',
  uiScale: '介面與文字縮放',
  fpsCap: '幀率上限',
  fps: { 0: '不限制', 30: '30 FPS', 60: '60 FPS', 120: '120 FPS' },
  colorBlind: '色盲輔助（警示顏色）',
  colorBlindModes: {
    off: '關閉',
    deuteranopia: '綠色弱（Deuteranopia）',
    protanopia: '紅色弱（Protanopia）',
    tritanopia: '藍色弱（Tritanopia）',
  },
  units: '單位',
  unitModes: { metric: '公制（m）', imperial: '英制（ft）' },
  unitsHelp: '套用於遊戲 HUD 與選單；機載 OSD 照真機維持公制。',
  fov: '外部視角視野（FOV）',
  fovHelp: '追蹤、環繞、俯視視角；機載鏡頭維持真實鏡頭。',
  comfort: [
    '動態舒適',
    '關閉追蹤視角的速度拉遠與視野放大、關閉外部鏡頭跟隨晃動，並降低手把震動與介面動畫。',
  ],
  haptic: '震動強度',
  hapticHelp: '手把震動回饋強度。動態舒適開啟時會再額外降低。',
});
// Resolutions offered in windowed mode, filtered to what fits the chosen display.
const RESOLUTIONS = [[1280, 720], [1280, 800], [1600, 900], [1920, 1080], [2560, 1440], [3840, 2160]];

function select(options, value, onChange) {
  const control = element('select');
  for (const [optionValue, label] of options) control.append(new Option(label, String(optionValue)));
  control.value = String(value);
  control.addEventListener('change', function changed() {
    onChange(control.value);
  });
  return control;
}

function range({ min, max, step, value, format, onInput }) {
  const wrap = element('div', 'menu-range');
  const control = element('input');
  control.type = 'range';
  control.min = String(min);
  control.max = String(max);
  control.step = String(step);
  control.value = String(value);
  const shown = element('output', 'menu-range-value', format(value));
  control.addEventListener('input', function moved() {
    shown.textContent = format(Number(control.value));
    onInput(Number(control.value));
  });
  wrap.append(control, shown);
  function show(value) {
    control.value = String(value);
    shown.textContent = format(value);
  }
  return { wrap, control, show };
}

function percent(value) {
  return `${Math.round(value * 100)}%`;
}

function resolutionOptions(display) {
  const width = display?.bounds?.width || display?.workArea?.width || 3840;
  const height = display?.bounds?.height || display?.workArea?.height || 2160;
  const sizes = RESOLUTIONS.filter(function fits([w, h]) {
    return w <= width && h <= height;
  });
  if (!sizes.length) sizes.push([Math.min(1280, width), Math.min(720, height)]);
  return sizes;
}

function pickResolution(sizes, current) {
  const key = `${current?.width}x${current?.height}`;
  if (sizes.some(function match([w, h]) {
    return `${w}x${h}` === key;
  })) return key;
  const last = sizes.at(-1);
  return `${last[0]}x${last[1]}`;
}

function monitorLabel(display, index) {
  const w = display.bounds?.width || display.workArea?.width || '?';
  const h = display.bounds?.height || display.workArea?.height || '?';
  return `${STRINGS.monitor} ${index + 1} · ${w} × ${h}`;
}

async function mountDesktopDisplay(pane, desktop, status) {
  let info = { displays: [], current: null };
  try {
    const raw = await desktop.display();
    // Older shells returned a bare array; keep that shape working.
    if (Array.isArray(raw)) info = { displays: raw, current: null };
    else info = { displays: raw?.displays || [], current: raw?.current || null };
  } catch {
    info = { displays: [], current: null };
  }
  if (!info.displays.length) return;
  const current = info.current || {
    mode: 'windowed',
    display: info.displays[0].id,
    width: info.displays.at(-1)?.bounds?.width || 1920,
    height: info.displays.at(-1)?.bounds?.height || 1080,
  };
  const monitor = select(info.displays.map(function option(display, index) {
    return [display.id, monitorLabel(display, index)];
  }), current.display, function onMonitor() {
    fillResolutions();
  });
  field(pane, { id: 'displayMonitor', label: STRINGS.monitor, control: monitor });
  const mode = select(Object.entries(STRINGS.modes), current.mode, function noop() {});
  field(pane, { id: 'displayMode', label: STRINGS.window, control: mode });
  const resolution = select([], '', function noop() {});
  field(pane, { id: 'displayResolution', label: STRINGS.resolution, control: resolution });
  function fillResolutions() {
    const selected = info.displays.find(function byId(entry) {
      return String(entry.id) === String(monitor.value);
    }) || info.displays[0];
    const sizes = resolutionOptions(selected);
    const keep = resolution.value || pickResolution(sizes, current);
    resolution.replaceChildren();
    for (const [width, height] of sizes) {
      resolution.append(new Option(`${width} × ${height}`, `${width}x${height}`));
    }
    resolution.value = sizes.some(function match([w, h]) {
      return `${w}x${h}` === keep;
    }) ? keep : pickResolution(sizes, current);
  }
  fillResolutions();
  const apply = element('button', 'menu-next', STRINGS.apply);
  apply.type = 'button';
  apply.id = 'displayApply';
  apply.addEventListener('click', async function applyDisplay() {
    const [width, height] = resolution.value.split('x').map(Number);
    try {
      const saved = await desktop.display({
        mode: mode.value,
        display: Number(monitor.value),
        width,
        height,
      });
      info.current = saved;
      status.textContent = STRINGS.applied;
    } catch (error) {
      status.textContent = STRINGS.failed.replace('{reason}', error?.message || '');
    }
  });
  pane.append(apply, status);
}

function mountBrowserFullscreen(pane) {
  const [label, help] = STRINGS.browserFullscreen;
  mountToggles(pane, [{
    id: 'displayFullscreen',
    label,
    help,
    checked: !!document.fullscreenElement,
    onChange(value) {
      if (value) document.documentElement.requestFullscreen?.().catch(function refused() {});
      else document.exitFullscreen?.().catch(function notFullscreen() {});
    },
  }]);
}

export function mountDisplaySettings(pane) {
  const prefs = getDisplayPrefs();
  const fidelity = getFidelity();
  const language = select(LANGUAGES.map(function option(entry) {
    return [entry.value, entry.label];
  }), getLanguage(), function chooseLanguage(value) {
    prefs.set('language', value);
  });
  field(pane, { id: 'displayLanguage', label: STRINGS.language, help: STRINGS.languageHelp, control: language });
  const desktop = window.rovDesktop;
  const status = element('p', 'menu-help');
  status.setAttribute('role', 'status');
  if (typeof desktop?.display === 'function') mountDesktopDisplay(pane, desktop, status);
  else mountBrowserFullscreen(pane);
  const brightness = range({
    min: LIMITS.brightness[0], max: LIMITS.brightness[1], step: 0.05, value: prefs.get('brightness'),
    format: percent,
    onInput(value) {
      prefs.set('brightness', value);
    },
  });
  field(pane, { id: 'displayBrightness', label: STRINGS.brightness, help: STRINGS.brightnessHelp,
    control: brightness.wrap });
  const scale = range({
    min: LIMITS.uiScale[0], max: LIMITS.uiScale[1], step: 0.05, value: prefs.get('uiScale'), format: percent,
    onInput(value) {
      prefs.set('uiScale', value);
    },
  });
  field(pane, { id: 'displayScale', label: STRINGS.uiScale, control: scale.wrap });
  const fps = select(FPS_CAPS.map(function option(cap) {
    return [cap, STRINGS.fps[cap]];
  }), prefs.get('fpsCap'), function chooseCap(value) {
    prefs.set('fpsCap', Number(value));
  });
  field(pane, { id: 'displayFps', label: STRINGS.fpsCap, control: fps });
  const colours = select(COLOR_BLIND_MODES.map(function option(mode) {
    return [mode, STRINGS.colorBlindModes[mode]];
  }), prefs.get('colorBlind'), function chooseColours(value) {
    prefs.set('colorBlind', value);
  });
  field(pane, { id: 'displayColorBlind', label: STRINGS.colorBlind, control: colours });
  const units = select(Object.entries(STRINGS.unitModes), prefs.get('units'), function chooseUnits(value) {
    prefs.set('units', value);
  });
  field(pane, { id: 'displayUnits', label: STRINGS.units, help: STRINGS.unitsHelp, control: units });
  const fov = range({
    min: 40, max: 90, step: 1, value: fidelity.get(EXTERNAL_FOV_ITEM) ?? 55,
    format(value) {
      return `${value}°`;
    },
    onInput(value) {
      fidelity.set(EXTERNAL_FOV_ITEM, value);
    },
  });
  field(pane, { id: 'displayFov', label: STRINGS.fov, help: STRINGS.fovHelp, control: fov.wrap });
  const [comfortLabel, comfortHelp] = STRINGS.comfort;
  mountToggles(pane, [{
    id: 'displayComfort',
    label: comfortLabel,
    help: comfortHelp,
    checked: !!fidelity.get(MOTION_COMFORT_ITEM),
    onChange(value) {
      fidelity.set(MOTION_COMFORT_ITEM, value);
    },
  }]);
  mountPreferenceRows(pane, ['reduceFlashes', 'subtitleSize', 'subtitleOpacity', 'speakerColor', 'radioDuration']);
  const haptic = range({
    min: LIMITS.hapticStrength[0],
    max: LIMITS.hapticStrength[1],
    step: 0.05,
    value: prefs.get('hapticStrength'),
    format: percent,
    onInput(value) {
      prefs.set('hapticStrength', value);
      inputPreferences.strength = value;
      saveInputPreferences();
    },
  });
  field(pane, {
    id: 'displayHaptic',
    label: STRINGS.haptic,
    help: STRINGS.hapticHelp,
    control: haptic.wrap,
  });
  // Changes made elsewhere (the fidelity panel lists the camera items too) show here as well.
  fidelity.subscribe(function syncCamera() {
    fov.show(fidelity.get(EXTERNAL_FOV_ITEM) ?? 55);
    const comfort = document.getElementById('displayComfort');
    if (comfort) comfort.checked = !!fidelity.get(MOTION_COMFORT_ITEM);
  });
  prefs.subscribe(function syncPrefs(values, id) {
    if (id === 'hapticStrength') haptic.show(values.hapticStrength);
  });
  return pane;
}
