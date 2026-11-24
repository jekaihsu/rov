// Read-only onboarding panel in the engineering drawer: checklist progress and context hints from telemetry.
import { actionGlyph, deviceFamily, padNames } from './input/glyphs.js';
import { hintText, actionKey, padLabel, axisChannel, pilotAxisKeys } from './input/bindings.js';
import { currentKeyRows, currentOperationMode } from './input/keyboard_layout.js';
import { controlLayoutLabel } from './control_layout.js';
import { localize } from './i18n/index.js';

const STORAGE_KEY = 'rov.pilotGuide.dismissed.v1';
const STRINGS = localize('pilot_guide', {
  title: '操作提示',
  practice: '首次潛航練習',
  steps: {
    unlock: '解除馬達鎖定',
    move: '操控移動一小段',
    depth: '啟用定深',
    light: '開啟照明',
  },
  bindingsSummary: '目前鍵位與視角',
  cameraHelp: ' 切換追蹤、環繞、俯視、機載視角。俯視時以滾輪縮放。',
  rebindHelp: '需更換手把或控制配置時，返回主選單。',
  dismiss: '收起提示，下次不自動展開',
  waiting: '等待連線；收到機器狀態後會顯示操作步驟。',
  replay: '回放',
  done: '已完成',
  open: '未完成',
  stepLabel: '{label}：{status}',
  modeUsb: 'USB 遙控器接管操作軸',
  modeLocal: '鍵盤／目前選用的手把',
  modeLine: '{layout} · {device}',
  channels: {
    left_ud: '左桿上下',
    left_lr: '左桿左右',
    right_ud: '右桿上下',
    right_lr: '右桿左右',
    left_wave: '左滾輪',
    right_wave: '右滾輪',
  },
  axes: {
    surge: '前進／後退',
    sway: '右移／左移',
    heave: '上升／下潛',
    yaw: '右轉／左轉',
  },
  hints: {
    replay: '正在回放錄製狀態。可用 {camera} 查看不同視角；駕駛練習在即時潛航中進行。',
    usbLost: 'USB 遙控器尚未連線。請先恢復連線，或返回主選單更換輸入裝置。',
    paused: '潛航已暫停。由房主恢復後再繼續操作。',
    latched: '控制中斷後已自動鎖定。等狀態同步，再用 {lock} 明確解除鎖定。',
    locked: '先確認前方淨空，再按 {lock} 解除馬達鎖定；停止操作時可再次鎖定。',
    remote: '目前由自動航線或 SDK 控制。先停止巡航，再練習手動駕駛。',
    move: '使用 {drive} 緩慢前後移動一小段，再回中。洋流仍會使機器漂移。',
    depth: '按 {depth} 啟用定深並回中升降桿。定深維持深度，水平方向仍可能漂移。',
    light: '按 {light} 開啟照明，再用 {camera} 切到機載視角觀察前方。',
    snagged: '纜線已接觸障礙；停止加速，觀察纜線路徑再退回。',
    current: '目前洋流較強。使用小幅持續修正，避免反覆大幅推桿。',
    done: '{scenario}：基礎操作已完成。可收起提示，依任務指引繼續探索。',
    scenarioFallback: '本次潛航',
  },
});

const AXIS_IDS = ['surge', 'sway', 'heave', 'yaw'];

function fill(template, values) {
  return String(template || '').replace(/\{(\w+)\}/g, function replace(_, key) {
    return values[key] ?? '';
  });
}

// Context line under the checklist: depends on telemetry, progress and the player's bound keys.
export function pilotGuideHint({
  readOnly = false,
  state,
  progress,
  keys = {},
  scenarioName = '',
} = {}) {
  if (!state) return STRINGS.waiting;
  const lock = keys.lock || 'Space';
  const depth = keys.depth || 'H';
  const light = keys.light || 'L';
  const camera = keys.camera || 'V';
  const drive = keys.drive || '';
  if (readOnly) return fill(STRINGS.hints.replay, { camera });
  if (state.controller && !state.controller.connected) return STRINGS.hints.usbLost;
  if (state.paused) return STRINGS.hints.paused;
  if (state.input_latched) return fill(STRINGS.hints.latched, { lock });
  if (state.locked) return fill(STRINGS.hints.locked, { lock });
  if (state.remote_control) return STRINGS.hints.remote;
  if (!progress?.move) return fill(STRINGS.hints.move, { drive });
  if (!progress?.depth) return fill(STRINGS.hints.depth, { depth });
  if (!progress?.light) return fill(STRINGS.hints.light, { light, camera });
  if (state.tether?.snagged_on?.length) return STRINGS.hints.snagged;
  if ((state.current_kn || 0) > 0.6) return STRINGS.hints.current;
  return fill(STRINGS.hints.done, {
    scenario: scenarioName || STRINGS.hints.scenarioFallback,
  });
}

export function installPilotGuide({ getState, getWorld, readOnly = false }) {
  const host = document.querySelector('.mission-tools') || document.querySelector('aside');
  if (!host) return { update() {}, dispose() {} };
  const root = document.createElement('section');
  root.className = 'pilot-guide';
  root.id = 'pilotGuide';
  root.innerHTML = `<style>
    .pilot-guide{margin:12px 0 0;padding-top:10px;border-top:1px solid var(--line,#1f3a4a)}
    .pilot-guide .pilot-toggle{width:100%;display:flex;justify-content:space-between;align-items:center;text-align:left;gap:8px}
    .pilot-guide .pilot-count{font:11px var(--f-data,monospace);color:var(--ink-dim,#7f99a8)}
    .pilot-guide .pilot-context{font-size:12px;line-height:1.65;color:var(--ink,#d6e4ec);margin:9px 0}
    .pilot-guide ol{list-style:none;padding:0;margin:8px 0;display:grid;grid-template-columns:1fr 1fr;gap:5px 9px;font-size:11px;color:var(--ink-dim,#7f99a8)}
    .pilot-guide li:before{content:'○';display:inline-block;width:16px}
    .pilot-guide li[data-complete=true]{color:var(--ok,#3ddc97)}
    .pilot-guide li[data-complete=true]:before{content:'✓'}
    .pilot-guide details{font-size:11px;line-height:1.7;margin-top:8px}
    .pilot-guide dl{margin:8px 0;display:grid;grid-template-columns:auto 1fr;gap:4px 8px}
    .pilot-guide dt{color:var(--ink-dim,#7f99a8)}.pilot-guide dd{margin:0}
    .pilot-guide .pilot-mode,.pilot-guide .pilot-shortcuts{font-size:11px;line-height:1.7;color:var(--ink-dim,#7f99a8);margin:7px 0}
    .pilot-guide .pilot-dismiss{font-size:11px;margin-top:5px;width:100%}
  </style>
  <button type="button" class="pilot-toggle" id="pilotGuideToggle" aria-controls="pilotGuideBody"><span>${STRINGS.title}</span><span class="pilot-count"></span></button>
  <div id="pilotGuideBody">
    <p class="pilot-context" role="status" aria-live="polite"></p>
    <ol aria-label="${STRINGS.practice}"><li data-step="unlock">${STRINGS.steps.unlock}</li><li data-step="move">${STRINGS.steps.move}</li><li data-step="depth">${STRINGS.steps.depth}</li><li data-step="light">${STRINGS.steps.light}</li></ol>
    <details><summary>${STRINGS.bindingsSummary}</summary><p class="pilot-mode"></p><dl></dl>
      <p class="pilot-shortcuts"><span class="pilot-keys"></span><br><span class="pilot-camera-key"></span>${STRINGS.cameraHelp}<br>${STRINGS.rebindHelp}</p>
    </details><button type="button" class="pilot-dismiss" id="pilotGuideDismiss">${STRINGS.dismiss}</button>
  </div>`;
  // Key captions come from the binding table, never from a second hand-written list.
  root.querySelector('.pilot-keys').textContent = hintText();
  let keyRowsVersion = 0;
  let family = 'keyboard';
  document.addEventListener('rov-key-rows', function keysChanged(event) {
    keyRowsVersion++;
    updateGlyphs();
    root.querySelector('.pilot-keys').textContent = hintText(event.detail);
  });
  const session = host.querySelector('.session-summary');
  if (session) session.after(root);
  else host.prepend(root);
  document.addEventListener('rov-input-device', function deviceChanged(event) {
    family = deviceFamily(event.detail);
    updateGlyphs();
  });
  function updateGlyphs() {
    let shortcuts = root.querySelector('.input-glyphs');
    if (!shortcuts) {
      shortcuts = document.createElement('span');
      shortcuts.className = 'input-glyphs';
      root.querySelector('.pilot-shortcuts').prepend(shortcuts);
    }
    root.querySelector('.pilot-camera-key').textContent = actionKey('camera', currentKeyRows());
    shortcuts.innerHTML = ['photo', 'record', 'depth', 'lock']
      .map(function glyphFor(action) {
        return actionGlyph(action, currentKeyRows(), family);
      }).join(' ');
  }
  updateGlyphs();
  const body = root.querySelector('#pilotGuideBody');
  const toggle = root.querySelector('#pilotGuideToggle');
  const context = root.querySelector('.pilot-context');
  const count = root.querySelector('.pilot-count');
  const modeLabel = root.querySelector('.pilot-mode');
  const table = root.querySelector('dl');
  let closed = readOnly;
  let disposed = false;
  let previousPosition = null;
  let previousCommand = false;
  let travel = 0;
  let identity = '';
  let lastTime = -1;
  let lastMapping = '';
  let progress = { unlock: false, move: false, depth: false, light: false };
  try {
    closed ||= localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    // Storage may be unavailable.
  }
  function show(open, remember = false) {
    body.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    if (remember) {
      try {
        localStorage.setItem(STORAGE_KEY, open ? '0' : '1');
      } catch {
        // Storage may be unavailable.
      }
    }
  }
  toggle.onclick = function toggled() {
    show(body.hidden, true);
  };
  root.querySelector('#pilotGuideDismiss').onclick = function dismissed() {
    show(false, true);
    toggle.focus();
  };
  show(!closed);

  function update(state = getState?.()) {
    if (disposed) return;
    if (!state) {
      context.textContent = pilotGuideHint({ state: null });
      return;
    }
    const key = `${state.vehicle_id || ''}:${state.model_id || ''}`;
    if (identity !== key || state.t < lastTime - 0.5) {
      identity = key;
      previousPosition = null;
      previousCommand = false;
      travel = 0;
      progress = { unlock: false, move: false, depth: false, light: false };
    }
    lastTime = state.t;
    const usb = !!state.controller;
    const mode = state.operation_mode || currentOperationMode();
    const surgeChannel = axisChannel('surge', mode)?.channel || 'right_ud';
    const mappingKey = `${mode}:${usb}:${keyRowsVersion}:${family}`;
    if (mappingKey !== lastMapping) {
      lastMapping = mappingKey;
      modeLabel.textContent = fill(STRINGS.modeLine, {
        layout: controlLayoutLabel(mode),
        device: usb ? STRINGS.modeUsb : STRINGS.modeLocal,
      });
      table.replaceChildren();
      for (const axis of AXIS_IDS) {
        const dt = document.createElement('dt');
        const dd = document.createElement('dd');
        const channel = axisChannel(axis, mode)?.channel;
        const row = currentKeyRows().find(function match(entry) {
          return entry.action === channel;
        });
        const pad = usb
          ? STRINGS.channels[channel]
          : padLabel(row?.pad, padNames(family) || undefined);
        const keys = pilotAxisKeys(axis, currentKeyRows(), mode).join(' / ');
        dt.textContent = STRINGS.axes[axis];
        dd.textContent = usb || !keys ? pad : `${keys} · ${pad}`;
        table.append(dt, dd);
      }
    }
    const commanded = !state.locked && !state.paused && !state.remote_control
      && Math.abs((state.rc?.[surgeChannel] ?? 1500) - 1500) > 80
      && (state.thrust || []).some(function thrusting(value) {
        return Math.abs(value) > 0.05;
      });
    if (!readOnly && !state.paused) {
      if (!state.locked && state.locked !== undefined) {
        progress.unlock = true;
        if (previousPosition && Array.isArray(state.pos) && commanded && previousCommand) {
          const distance = Math.hypot(...state.pos.map(function delta(value, i) {
            return value - previousPosition[i];
          }));
          if (distance < 0.5) travel += distance;
          if (travel > 0.35) progress.move = true;
        }
      }
      if (state.keep_depth && state.depth_hold != null) progress.depth = true;
      if ((state.rc?.right_switch ?? 0) > 0) progress.light = true;
    }
    previousPosition = Array.isArray(state.pos) ? [...state.pos] : null;
    previousCommand = commanded;
    const completed = Object.values(progress).filter(Boolean).length;
    const progressText = readOnly ? STRINGS.replay : `${completed} / 4`;
    if (count.textContent !== progressText) count.textContent = progressText;
    root.querySelector('ol').hidden = readOnly;
    for (const [step, done] of Object.entries(progress)) {
      const item = root.querySelector(`[data-step="${step}"]`);
      if (item.dataset.complete !== String(done)) {
        item.dataset.complete = String(done);
        item.setAttribute('aria-label', fill(STRINGS.stepLabel, {
          label: item.textContent,
          status: done ? STRINGS.done : STRINGS.open,
        }));
      }
    }
    const rows = currentKeyRows();
    const hint = pilotGuideHint({
      readOnly,
      state,
      progress,
      keys: {
        lock: actionKey('lock', rows) || 'Space',
        depth: actionKey('depth', rows) || 'H',
        light: actionKey('light', rows) || 'L',
        camera: actionKey('camera', rows) || 'V',
        drive: usb
          ? STRINGS.channels[surgeChannel]
          : pilotAxisKeys('surge', rows, mode).join(' / '),
      },
      scenarioName: getWorld?.()?.scenario?.name || '',
    });
    if (context.textContent !== hint) context.textContent = hint;
  }
  update();
  return {
    update,
    dispose() {
      disposed = true;
      root.remove();
    },
  };
}
