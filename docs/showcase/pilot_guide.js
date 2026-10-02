// Read-only onboarding: every check comes from received simulator telemetry.
const STORAGE_KEY = 'rov.pilotGuide.dismissed.v1';
const CHANNELS = {
  left_ud: ['W / S', '左桿上下'], left_lr: ['D / A', '左桿左右'],
  right_ud: ['↑ / ↓', '右桿上下'], right_lr: ['→ / ←', '右桿左右'],
  left_wave: ['E / Q', '左滾輪'], right_wave: ['C / Z', '右滾輪'],
};
// Matches app.js MAP and qysim/rc.py; order is surge, sway, heave, yaw.
const MODES = {
  ROV_USA: ['right_ud', 'right_wave', 'left_wave', 'left_lr'],
  ROV_JPN: ['left_ud', 'right_wave', 'left_wave', 'left_lr'],
  ROV_CHN: ['left_ud', 'right_wave', 'left_wave', 'right_lr'],
  UAV_USA: ['right_ud', 'right_lr', 'left_ud', 'left_lr'],
  UAV_JPN: ['left_ud', 'right_lr', 'right_ud', 'left_lr'],
  UAV_CHN: ['left_ud', 'left_lr', 'right_ud', 'right_lr'],
};

export function installPilotGuide({getState, getWorld, readOnly = false}) {
  const host = document.querySelector('.mission-tools') || document.querySelector('aside');
  if (!host) return {update() {}, dispose() {}};
  const root = document.createElement('section');
  root.className = 'pilot-guide'; root.id = 'pilotGuide';
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
  <button type="button" class="pilot-toggle" id="pilotGuideToggle" aria-controls="pilotGuideBody"><span>操作提示</span><span class="pilot-count"></span></button>
  <div id="pilotGuideBody">
    <p class="pilot-context" role="status" aria-live="polite"></p>
    <ol aria-label="首次潛航練習"><li data-step="unlock">解除馬達鎖定</li><li data-step="move">操控移動一小段</li><li data-step="depth">啟用定深</li><li data-step="light">開啟照明</li></ol>
    <details><summary>目前鍵位與視角</summary><p class="pilot-mode"></p><dl></dl>
      <p class="pilot-shortcuts">Space 鎖定／解鎖 · H 定深 · L 燈光<br>V 切換追蹤、環繞、俯視、機載視角。俯視時以滾輪縮放。<br>需更換手柄或控制配置時，返回主選單。</p>
    </details><button type="button" class="pilot-dismiss" id="pilotGuideDismiss">收起提示，下次不自動展開</button>
  </div>`;
  const session = host.querySelector('.session-summary');
  if (session) session.after(root); else host.prepend(root);
  const body = root.querySelector('#pilotGuideBody'), toggle = root.querySelector('#pilotGuideToggle');
  const context = root.querySelector('.pilot-context'), count = root.querySelector('.pilot-count');
  const modeLabel = root.querySelector('.pilot-mode'), table = root.querySelector('dl');
  let closed = readOnly, disposed = false, previousPosition = null, previousCommand = false;
  let travel = 0, identity = '', lastTime = -1, lastMapping = '';
  let progress = {unlock: false, move: false, depth: false, light: false};
  try { closed ||= localStorage.getItem(STORAGE_KEY) === '1'; } catch {}
  function show(open, remember = false) {
    body.hidden = !open; toggle.setAttribute('aria-expanded', String(open));
    if (remember) try { localStorage.setItem(STORAGE_KEY, open ? '0' : '1'); } catch {}
  }
  toggle.onclick = () => show(body.hidden, true);
  root.querySelector('#pilotGuideDismiss').onclick = () => { show(false, true); toggle.focus(); };
  show(!closed);

  function update(state = getState?.()) {
    if (disposed) return;
    if (!state) { context.textContent = '等待連線；收到機器狀態後會顯示操作步驟。'; return; }
    const key = `${state.vehicle_id || ''}:${state.model_id || ''}`;
    if (identity !== key || state.t < lastTime - .5) {
      identity = key; previousPosition = null; previousCommand = false; travel = 0;
      progress = {unlock: false, move: false, depth: false, light: false};
    }
    lastTime = state.t;
    const usb = !!state.controller, mode = state.operation_mode || 'ROV_USA';
    const channels = MODES[mode] || MODES.ROV_USA;
    const mappingKey = `${mode}:${usb}`;
    if (mappingKey !== lastMapping) {
      lastMapping = mappingKey;
      modeLabel.textContent = `${mode === 'UAV_CHN' ? 'ROV 雙桿' : mode} · ${usb ? 'USB 遙控器接管操作軸' : '鍵盤／目前選用的手柄'}`;
      table.replaceChildren();
      ['前進／後退', '右移／左移', '上浮／下潛', '右轉／左轉'].forEach((label, i) => {
        const dt = document.createElement('dt'), dd = document.createElement('dd');
        dt.textContent = label;
        dd.textContent = usb ? CHANNELS[channels[i]][1] : `${CHANNELS[channels[i]][0]} · ${CHANNELS[channels[i]][1]}`;
        table.append(dt, dd);
      });
    }
    const commanded = !state.locked && !state.paused && !state.remote_control &&
      Math.abs((state.rc?.[channels[0]] ?? 1500) - 1500) > 80 &&
      (state.thrust || []).some(value => Math.abs(value) > .05);
    if (!readOnly && !state.paused) {
      if (!state.locked && state.locked !== undefined) {
        progress.unlock = true;
        if (previousPosition && Array.isArray(state.pos) && commanded && previousCommand) {
          const distance = Math.hypot(...state.pos.map((value, i) => value - previousPosition[i]));
          if (distance < .5) travel += distance; // Ignore resets/teleports and idle drift.
          if (travel > .35) progress.move = true;
        }
      }
      if (state.keep_depth && state.depth_hold != null) progress.depth = true;
      if ((state.rc?.right_switch ?? 0) > 0) progress.light = true;
    }
    previousPosition = Array.isArray(state.pos) ? [...state.pos] : null;
    previousCommand = commanded;
    const completed = Object.values(progress).filter(Boolean).length;
    const progressText = readOnly ? '回放' : `${completed} / 4`;
    if (count.textContent !== progressText) count.textContent = progressText;
    root.querySelector('ol').hidden = readOnly;
    for (const [step, done] of Object.entries(progress)) {
      const item = root.querySelector(`[data-step="${step}"]`);
      if (item.dataset.complete !== String(done)) {
        item.dataset.complete = String(done);
        item.setAttribute('aria-label', `${item.textContent}：${done ? '已完成' : '未完成'}`);
      }
    }
    const driveKey = usb ? CHANNELS[channels[0]][1] : CHANNELS[channels[0]][0];
    let hint;
    if (readOnly) hint = '正在回放錄製狀態。可用 V 查看不同視角；駕駛練習在即時潛航中進行。';
    else if (usb && !state.controller.connected) hint = 'USB 遙控器尚未連線。請先恢復連線，或返回主選單更換輸入裝置。';
    else if (state.paused) hint = '潛航已暫停。由房主恢復後再繼續操作。';
    else if (state.input_latched) hint = '控制中斷後已自動鎖定。等狀態同步，再用 Space 明確解除鎖定。';
    else if (state.locked) hint = '先確認前方淨空，再按 Space 解除馬達鎖定；停止操作時可再次鎖定。';
    else if (state.remote_control) hint = '目前由自動航線或 SDK 控制。先停止巡航，再練習手動駕駛。';
    else if (!progress.move) hint = `使用 ${driveKey} 緩慢前後移動一小段，再回中。洋流仍會使機器漂移。`;
    else if (!progress.depth) hint = '按 H 啟用定深並回中升降桿。定深維持深度，水平方向仍可能漂移。';
    else if (!progress.light) hint = '按 L 開啟照明，再用 V 切到機載視角觀察前方。';
    else if (state.tether?.snagged_on?.length) hint = '纜線已接觸障礙；停止加速，觀察纜線路徑再退回。';
    else if ((state.current_kn || 0) > .6) hint = '目前洋流較強。使用小幅持續修正，避免反覆大幅推桿。';
    else hint = `${getWorld?.()?.scenario?.name || '本次潛航'}：基礎操作已完成。可收起提示，依任務指引繼續探索。`;
    if (context.textContent !== hint) context.textContent = hint;
  }
  update();
  return {update, dispose() { disposed = true; root.remove(); }};
}
