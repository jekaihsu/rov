// Full flight presentation and nonblocking peek cards; never sends vehicle controls.
// Chooses the line instrument or the camera OSD (hud_style.js) and feeds both the same smoothed read-outs
// taken from the delayed display state.
import { smoothHeading, drawHeadingTape, headingLabel } from './compass.js';
import { forwardRange } from './range.js';
import { drawFlightAttitude } from './attitude.js';
import { drawDepthLadder } from './depth_ladder.js';
import { drawMinimap } from './minimap.js';
import { installOsd, updateOsd } from './osd.js';
import { resolveHudStyle } from './hud_style.js';
import { getFidelity, fidelityText } from '../fidelity.js';
import { installFidelityPanel } from '../fidelity_panel.js';
import { BINDINGS, actionKey, bindingRow, hintText, layoutLabel, pilotAxisKeys } from '../input/bindings.js';
import { keyboardLayout } from '../input/keyboard_layout.js';
import { assistPill, dvlReason } from './assist_pill.js';
import { updateSystemStatus, batteryApplies } from './system_status.js';
import { pilotReadings } from './sensor_view.js';
const STRINGS = {
  sonarSource: '聲納',
  close: '收起工程面板', depth: '深度', altitude: '離底', engineering: '工程 Tab',
  density: ['極簡', '標準', '完整'],
  view: '切換視角 V', locked: '馬達鎖定', unlocked: '馬達解鎖',
  unlockHint: '按 {key} / 手把 Y 解鎖',
  axes: [['surge', '前進／後退'], ['sway', '右移／左移'], ['heave', '上升／下潛'], ['yaw', '右轉／左轉']],
  hide: '切換 HUD', north: '北朝上', head: '機頭朝上',
  cards: ['任務與目標', '載具系統', '地圖與隊友', '鍵位提示'],
  cable: '纜線', battery: '電量', tension: '張力', light: '燈光',
  danger: '危險：纜線斷裂', warn: '注意：纜線張力', near: '注意：接近海床',
  obstacleDanger: '危險：障礙距離不足', lowBattery: '提示：電量偏低',
  forward: '前方估距', controller: 'USB 控制器已連線', dvlLost: '注意：DVL 失去底鎖',
  fidelity: {real: 'presetReal', assisted: 'presetAssisted', custom: 'presetCustom'},
};
const $ = id => document.getElementById(id);
let ready = false;
let active = -1;
let deadline = 0;
let pressedAt = 0;
let held = false;
let previous = [];
let lastWarning = '';
let missionKey;
let peerCount;
let operationMode;
let engineeringHeld = false;
let north = true;
let density = 1;
const values = {};
// Presentation keys are declared in the binding table; the HUD only listens for them.
const CARD_KEYS = ['up', 'left', 'right', 'down'].map(action => bindingRow(action).keys[0]);
const DRAWER_KEYS = bindingRow('engineering').keys;
let hudStyle = '';
function storage(key, fallback) {
  try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, value); } catch { /* Private browsing. */ }
}
function drawer() {
  $('engineering').hidden = !$('engineering').hidden;
  save('rov.hud.drawer', String(!$('engineering').hidden));
}
function add(id, content) {
  const el = document.createElement('div');
  el.id = id;
  el.className = 'flight';
  el.innerHTML = content;
  $('vp').append(el);
  return el;
}
function showEventCard(index) {
  active = index;
  deadline = performance.now() + 3000;
}
function down(index) {
  if (active === index) {
    active = -1;
    held = false;
    return;
  }
  active = index;
  pressedAt = performance.now();
  deadline = pressedAt + 3000;
  held = true;
  $('flightPeek').classList.add('visible');
}
function up(index) {
  if (index !== active) return;
  if (held && performance.now() - pressedAt > 250) active = -1;
  held = false;
}
// Semantic directions come from the selected, normalized and remappable input device.
export function readHUDButtons(actions = {}) {
  return ['up', 'left', 'right', 'down'].map(name => (actions[name] || 0) > .5);
}
function setDensity() {
  density = getFidelity().get('hudDensity');
  document.body.classList.toggle('hud-minimal', density === 0);
  toolIcon($('flightDensity'), 'density', STRINGS.density[density]);
}
function showFidelity() {
  const chip = $('flightFidelity');
  if (!chip) return;
  const preset = getFidelity().preset;
  chip.textContent = fidelityText(STRINGS.fidelity[preset]);
  chip.dataset.preset = preset;
}
// The pill states what the pilot selected; the status chip says when the simulator is not flying it.
function showAssist(s) {
  const fidelity = getFidelity();
  const pill = assistPill(s, {level: fidelity.get('assistLevel'), profile: fidelity.get('flightProfile')});
  const chip = $('flightAssist');
  const status = $('flightAssistStatus');
  if (chip.textContent !== pill.text) chip.textContent = pill.text;
  status.hidden = !pill.status;
  if (status.textContent !== pill.status) status.textContent = pill.status;
  status.dataset.tone = pill.tone;
  status.title = pill.help;
}
function toolIcon(button, icon, label) {
  button.title = label;
  button.setAttribute('aria-label', label);
  if (button.querySelector('svg')) return;
  button.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24">'
    + `<use href="/hud/icons.svg#${icon}"></use></svg>`;
}
function initialize() {
  ready = true;
  const panel = document.createElement('section');
  panel.id = 'engineering';
  panel.setAttribute('aria-label', STRINGS.engineering);
  panel.hidden = storage('rov.hud.drawer', 'false') !== 'true';
  document.body.append(panel);
  const close = document.createElement('button');
  close.textContent = STRINGS.close;
  close.onclick = drawer;
  panel.append(close);
  installFidelityPanel(panel);
  panel.append(document.querySelector('.topbar'), ...document.querySelectorAll('.rack'));
  panel.querySelectorAll('.mission-tools > div[hidden]').forEach(function revealSettings(el) {
    el.hidden = false;
  });
  add('flightDepth', `<canvas id="flightLadder"></canvas><div class="depth-text"><small>${STRINGS.depth}</small>
    <div><b id="flightDepthValue">—</b><u>m</u></div>
    <small>${STRINGS.altitude} <span id="flightAltitude">—</span> m</small></div>`);
  add('flightAttitude', '<canvas id="flightADI"></canvas>');
  const headingValue = document.createElement('div');
  headingValue.id = 'flightHeading';
  $('tape').before(headingValue);
  installOsd($('vp'));
  add('flightMission', '');
  add('flightRange', '');
  add('flightController', '');
  add('flightMapBox', `<canvas id="flightMap"></canvas>
    <button id="flightMapMode">${STRINGS.north}</button>`);
  add('flightWarning', '').setAttribute('role', 'status');
  add('flightPeek', '<strong></strong><p></p><canvas hidden></canvas>');
  add('flightTools', `<button id="flightDrawer">${STRINGS.engineering}</button>
    <button id="flightDensity"></button><button id="flightHide">${STRINGS.hide}</button>`);
  $('flightTools').append($('camBtn'));
  toolIcon($('flightDrawer'), 'engineering', STRINGS.engineering);
  toolIcon($('flightHide'), 'hud', STRINGS.hide);
  $('flightDrawer').onclick = drawer;
  $('flightMapMode').onclick = function toggleNorth() {
    north = !north;
    this.textContent = north ? STRINGS.north : STRINGS.head;
  };
  setDensity();
  getFidelity().subscribe(function fidelityChanged() {
    setDensity();
    showFidelity();
  });
  $('flightDensity').onclick = function cycleDensity() {
    getFidelity().set('hudDensity', (density + 1) % 3);
  };
  $('flightHide').onclick = function hideHUD() { document.body.classList.toggle('hud-hidden'); };
  document.addEventListener('keydown', function keyDown(event) {
    if (event.target.closest('input,select,textarea,[contenteditable=true]')) return;
    if (DRAWER_KEYS.includes(event.code)) {
      event.preventDefault();
      if (!event.repeat) drawer();
    }
    const index = CARD_KEYS.indexOf(event.code);
    if (index >= 0 && !event.repeat) down(index);
  });
  document.addEventListener('keyup', function keyUp(event) {
    const index = CARD_KEYS.indexOf(event.code);
    if (index >= 0) up(index);
  });
  window.addEventListener('blur', function blur() {
    held = false;
    active = -1;
  });
}
function smooth(key, target, dt) {
  values[key] = (values[key] ?? target) + (target - (values[key] ?? target)) * (1 - Math.exp(-dt * 12));
  return values[key];
}
// Help card: the stick mapping of the current control layout, then every key from the binding table.
// Movement first, named by what it does (前進／後退 W / S), then every other key from the binding table.
function keyCardText(input) {
  const rows = input.keyRows || BINDINGS;
  const mode = input.operationMode || 'ROV_USA';
  const lines = [layoutLabel(keyboardLayout())];
  for (const [axis, label] of STRINGS.axes) {
    const keys = pilotAxisKeys(axis, rows, mode);
    if (keys.length) lines.push(`${label} ${keys.join(' / ')}`);
  }
  lines.push(hintText({ bindings: input.bindings, rows, operationMode: mode }));
  return lines.filter(Boolean).join('\n');
}
function lockKey(input) {
  return actionKey('lock', input.keyRows || BINDINGS) || 'Space';
}
function currentStyle() {
  const fidelity = getFidelity();
  return resolveHudStyle({
    setting: fidelity.get('hudStyle'), preset: fidelity.preset, view: $('camBtn')?.dataset.mode || 'onboard',
  });
}
function applyStyle() {
  const next = currentStyle();
  if (next === hudStyle) return;
  hudStyle = next;
  document.body.dataset.hudStyle = next;
}
function addReadouts() {
  document.querySelector('.readout').insertAdjacentHTML('beforeend',
    `<span><i>${STRINGS.cable}</i><b id="flightCable"></b>m</span>`
    + `<span><i>${STRINGS.tension}</i><b id="flightTension"></b>N</span>`
    + `<span><i>${STRINGS.light}</i><b id="flightLight"></b>/ 2</span>`
    + `<span><i>${STRINGS.battery}</i><b id="flightBattery"></b>%</span>`);
  for (const id of ['rDepth', 'rAlt', 'rCur']) $(id).parentElement.style.display = 'none';
  const chip = document.createElement('span');
  chip.id = 'flightAssist';
  chip.className = 'chip';
  const fidelityChip = document.createElement('span');
  fidelityChip.id = 'flightFidelity';
  fidelityChip.className = 'chip';
  const status = document.createElement('span');
  status.id = 'flightAssistStatus';
  status.className = 'chip';
  status.setAttribute('role', 'status');
  document.querySelector('.chips').append(fidelityChip, chip, status);
  showFidelity();
}
// The DVL warning names the reason in the player's words when the sensor layer reports one.
function dvlWarning(s) {
  const reason = dvlReason(s);
  return reason ? `${STRINGS.dvlLost}（${reason.status}）` : STRINGS.dvlLost;
}
function setText(el, text) {
  if (el.textContent !== text) el.textContent = text;
}
// Smoothed read-outs shared by both presentations.
// sensed: pilotReadings() — sensor estimates in the real preset, simulator truth otherwise.
function readings(s, w, dt, sensed) {
  const alt = sensed.altitude;
  return {
    alt: alt == null ? null : smooth('alt', alt, dt),
    altWarn: alt != null && alt < 1.5,
    depth: smooth('depth', sensed.depth, dt),
    heading: smoothHeading(sensed.heading, dt),
    speed: sensed.speedKn == null ? null : smooth('speed', sensed.speedKn, dt),
    cable: smooth('cable', s.tether?.length || 0, dt),
    tension: smooth('tension', s.tether?.tension_rov || 0, dt),
    battery: smooth('battery', s.battery ?? 0, dt),
    light: s.rc?.right_switch || 0,
  };
}
function updateLine(r, s, w) {
  setText($('flightHeading'), `${headingLabel(r.heading)}°`);
  drawHeadingTape($('tape'), r.heading);
  setText($('flightDepthValue'), r.depth.toFixed(1));
  setText($('flightAltitude'), r.alt == null ? '—' : r.alt.toFixed(1));
  $('flightAltitude').parentElement.classList.toggle('warn', r.altWarn);
  drawDepthLadder($('flightLadder'), {
    depth: r.depth, seabed: w?.seabed_depth ?? null, hold: s.keep_depth ? s.depth_hold : null, warn: r.altWarn,
  });
  if (density > 0) drawFlightAttitude($('flightADI'), s.euler);
}
function updateReadout(r, s) {
  setText($('rSpd'), r.speed == null ? '—' : r.speed.toFixed(2));
  setText($('flightCable'), r.cable.toFixed(1));
  setText($('flightTension'), r.tension.toFixed(0));
  setText($('flightLight'), String(r.light));
  setText($('flightBattery'), r.battery.toFixed(0));
  $('flightCable').parentElement.classList.toggle('warn', !!s.tether?.warn);
  $('flightTension').parentElement.classList.toggle('warn', !!s.tether?.warn);
  $('flightBattery').parentElement.classList.toggle('warn', s.battery < 20);
  $('flightBattery').parentElement.hidden = !batteryApplies(s);
  updateSystemStatus(s);
}
export function updateFlightHUD(s, w, dt, input = {}) {
  if (!ready) initialize();
  if (!s?.pos) return;
  applyStyle();
  toolIcon($('camBtn'), 'camera', $('camBtn').dataset.label || STRINGS.view);
  $('lockBadge').querySelector('b').textContent = s.locked ? STRINGS.locked : STRINGS.unlocked;
  const unlockHint = s.locked ? STRINGS.unlockHint.replace('{key}', lockKey(input)) : '';
  $('lockBadge').querySelector('span').textContent = unlockHint;
  $('flightTools').classList.toggle('controller-visible', !!input.active);
  const sensed = pilotReadings(s, w);
  // One forward range: the imaging sonar's centre beams while it is scanning (labelled as such), otherwise the
  // sensor layer's forward echo, falling back to the geometric estimate in truth mode.
  const range = s.sonar || sensed.range === undefined ? forwardRange(s, w) : sensed.range;
  const rangeSource = s.sonar ? STRINGS.sonarSource : STRINGS.forward;
  $('flightRange').textContent = range == null ? '' : `${rangeSource} ${range.toFixed(1)} m`;
  $('flightRange').dataset.level = range < .5 ? 'danger' : 'warning';
  $('flightController').textContent = s.controller ? STRINGS.controller : '';
  const alt = sensed.altitude;
  if (!$('flightCable')) addReadouts();
  const r = readings(s, w, dt, sensed);
  updateReadout(r, s);
  showAssist(s);
  if (hudStyle === 'osd') {
    updateOsd(r, s, w, {
      assistLevel: getFidelity().get('assistLevel'), assistStatus: $('flightAssistStatus').hidden ? ''
        : $('flightAssistStatus').textContent, lockKey: lockKey(input),
    });
  } else {
    updateLine(r, s, w);
  }
  const objective = s.expedition?.active?.steps?.find(item => !item.completed)
    || s.mission?.targets?.find(item => !item.done)
    || s.score?.objectives?.find(item => !item.done);
  $('flightMission').textContent = (objective?.label || objective?.name || $('scoreState').textContent)
    + (objective?.progress != null ? ` · ${Math.round(objective.progress * 100)}%` : '');
  const nearDanger = alt != null && alt < .25 || range != null && range < .25;
  const danger = !!s.tether?.broken || nearDanger;
  const nextMissionKey = [s.mission?.mode, objective?.id, objective?.label, s.score?.current_index].join(':');
  const nextPeerCount = s.vehicles?.length || 1;
  if (!held) {
    if (missionKey != null && missionKey !== nextMissionKey) showEventCard(0);
    if (peerCount != null && peerCount !== nextPeerCount) showEventCard(2);
    if (operationMode != null && operationMode !== s.operation_mode) showEventCard(3);
  }
  missionKey = nextMissionKey;
  peerCount = nextPeerCount;
  operationMode = s.operation_mode;
  const warning = s.tether?.broken ? STRINGS.danger : nearDanger ? STRINGS.obstacleDanger
    : s.tether?.warn ? STRINGS.warn
    : alt != null && alt < 1 || range != null && range < 1 ? STRINGS.near
      : batteryApplies(s) && s.battery < 20 ? STRINGS.lowBattery
        : sensed.dvlLost && s.rc?.assist ? dvlWarning(s) : '';
  $('flightWarning').textContent = warning;
  $('flightWarning').dataset.level = danger ? 'danger'
    : warning === STRINGS.lowBattery ? 'info' : 'warning';
  document.body.classList.toggle('hud-danger', danger);
  if (warning && warning !== lastWarning) {
    if (!held) showEventCard(1);
    input.pulse?.(danger ? 'hard' : 'tension');
  }
  lastWarning = warning;
  // The input layer reports the long press as one level; a short press of the same button never arrives here.
  const engineering = (input.actions?.engineering || 0) > .5;
  if (engineering && !engineeringHeld) drawer();
  engineeringHeld = engineering;
  const buttons = readHUDButtons(input.actions);
  buttons.forEach(function checkButton(pressed, index) {
    if (pressed && !previous[index]) down(index);
    if (!pressed && previous[index]) up(index);
  });
  previous = buttons;
  if (!held && performance.now() > deadline) active = -1;
  const card = $('flightPeek');
  card.classList.toggle('visible', active >= 0 || density === 2);
  document.body.classList.toggle('hud-peek', active >= 0);
  const index = active < 0 ? 1 : active;
  card.querySelector('strong').textContent = STRINGS.cards[index];
  card.dataset.card = String(index);
  const sources = [
    ['brief', 'objs', 'missionStatus'], ['thrBars', 'tState', 'tRov', 'gBat', 'damage'], ['activeRoomName'], [],
  ];
  card.querySelector('p').textContent = index === 3
    ? keyCardText(input)
    : sources[index].map(id => $(id)?.textContent || '').join('\n');
  if (index === 1) {
    const thrusters = Array.from($('thrBars').children).map(function thrusterRow(row) {
      return Array.from(row.children).map(el => el.textContent).filter(Boolean).join(' · ');
    });
    card.querySelector('p').textContent = [
      warning, ...thrusters,
      `${STRINGS.cable} ${$('flightCable').textContent} m · ${$('tRov').textContent}`,
      `${STRINGS.battery} ${$('flightBattery').textContent}%`, $('damage').textContent,
    ].filter(Boolean).join('\n');
  }
  if (index === 0 && s.mission?.targets?.length) {
    card.querySelector('p').textContent = document.querySelector('.mission-mode-targets')?.textContent || '';
  }
  card.querySelector('canvas').hidden = index !== 2;
  if (index === 2) drawMinimap(card.querySelector('canvas'), s, w, north);
  if (density > 0) drawMinimap($('flightMap'), s, w, north);
}
