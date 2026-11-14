// Full flight presentation and nonblocking peek cards; never sends vehicle controls.
import { drawFlightCompass } from './compass.js';
import { forwardRange } from './range.js';
import { drawFlightAttitude } from './attitude.js';
import { getFidelity, fidelityText } from '../fidelity.js';
import { installFidelityPanel } from '../fidelity_panel.js';
import { bindingRow, hintText } from '../input/bindings.js';
import { assistPill } from './assist_pill.js';
const STRINGS = {
  close: '收起工程面板', depth: '深度', altitude: '離底', engineering: '工程 Tab',
  density: ['極簡', '標準', '完整'],
  view: '切換視角 V', locked: '馬達鎖定', unlocked: '馬達解鎖',
  unlockHint: '按 Space / 手把 Y 解鎖',
  hide: '切換 HUD', north: '北朝上', head: '機頭朝上',
  cards: ['任務與目標', '載具系統', '地圖與隊友', '鍵位提示'],
  cable: '纜線', battery: '電量',
  danger: '危險：纜線斷裂', warn: '注意：纜線張力', near: '注意：接近海床',
  obstacleDanger: '危險：障礙距離不足', lowBattery: '提示：電量偏低',
  forward: '前方估距', controller: 'USB 控制器已連線',
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
  add('flightDepth', `${STRINGS.depth}<br><b id="flightDepthValue">—</b> m<br>${STRINGS.altitude}
    <span id="flightAltitude">—</span> m<br><meter id="flightClearance" min="0" max="3"></meter>`);
  add('flightAttitude', '<canvas id="flightADI" width="520" height="240" style="width:100%"></canvas>');
  add('flightMission', '');
  add('flightRange', '');
  add('flightController', '');
  add('flightMapBox', `<canvas id="flightMap" width="336" height="288"></canvas>
    <button id="flightMapMode">${STRINGS.north}</button>`);
  add('flightWarning', '').setAttribute('role', 'status');
  add('flightPeek', '<strong></strong><p></p><canvas width="336" height="288" hidden></canvas>');
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
function drawMap(canvas, s, w) {
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save();
  ctx.translate(canvas.width / 2, canvas.height / 2);
  const heading = (s.euler?.[2] || 0) * Math.PI / 180;
  if (!north) ctx.rotate(-heading);
  function point(p) { return [(p[1] - s.pos[1]) * 5, -(p[0] - s.pos[0]) * 5]; }
  function line(points, color) {
    ctx.strokeStyle = color;
    ctx.beginPath();
    points.forEach(function vertex(p, i) {
      const [x, y] = point(p);
      if (i) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    });
    ctx.stroke();
  }
  for (const ob of w?.obstacles || []) {
    if (ob.p0 && ob.p1) line([ob.p0, ob.p1], '#8fa6b2');
    if (ob.center) {
      const [x, y] = point(ob.center);
      ctx.strokeStyle = '#8fa6b2';
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate((ob.yaw_deg || 0) * Math.PI / 180);
      ctx.strokeRect(-ob.half[1] * 5, -ob.half[0] * 5, ob.half[1] * 10, ob.half[0] * 10);
      ctx.restore();
    }
    if (ob.type === 'wall') {
      const angle = ob.normal_deg * Math.PI / 180;
      const tangent = [-Math.sin(angle) * ob.width / 2, Math.cos(angle) * ob.width / 2];
      line([
        [ob.point[0] - tangent[0], ob.point[1] - tangent[1]],
        [ob.point[0] + tangent[0], ob.point[1] + tangent[1]],
      ], '#8fa6b2');
    }
  }
  line(s.tether?.nodes || [], '#4fd1e0');
  for (const target of s.mission?.targets || w?.objectives || []) {
    if (!target.point) continue;
    const [x, y] = point(target.point);
    ctx.strokeStyle = '#f2b84b';
    ctx.strokeRect(x - 4, y - 4, 8, 8);
  }
  for (const peer of s.vehicles || []) {
    if (!peer.pos || (peer.vehicle_id || peer.id) === s.vehicle_id) continue;
    const [x, y] = point(peer.pos);
    ctx.fillStyle = '#5fd38a';
    ctx.fillRect(x - 3, y - 3, 6, 6);
  }
  ctx.rotate(heading);
  ctx.fillStyle = '#e8f1f5';
  ctx.beginPath();
  ctx.moveTo(0, -10);
  ctx.lineTo(-6, 7);
  ctx.lineTo(6, 7);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}
// Help card: the stick mapping of the current control layout, then every key from the binding table.
function keyCardText(bindings) {
  const guide = $('pilotGuide');
  const lines = [guide?.querySelector('.pilot-mode')?.textContent || ''];
  for (const term of guide?.querySelectorAll('dt') || []) {
    lines.push(`${term.textContent} ${term.nextElementSibling?.textContent || ''}`);
  }
  lines.push(hintText({ bindings }));
  return lines.filter(Boolean).join('\n');
}
export function updateFlightHUD(s, w, dt, input = {}) {
  if (!ready) initialize();
  if (!s?.pos) return;
  toolIcon($('camBtn'), 'camera', STRINGS.view);
  $('lockBadge').querySelector('b').textContent = s.locked ? STRINGS.locked : STRINGS.unlocked;
  $('lockBadge').querySelector('span').textContent = s.locked ? STRINGS.unlockHint : '';
  $('flightTools').classList.toggle('controller-visible', !!input.active);
  const range = forwardRange(s, w);
  $('flightRange').textContent = range == null ? '' : `${STRINGS.forward} ${range.toFixed(1)} m`;
  $('flightRange').style.color = range < .5 ? 'var(--danger)' : 'var(--warn)';
  $('flightController').textContent = s.controller ? STRINGS.controller : '';
  const alt = w ? w.seabed_depth - s.pos[2] : null;
  $('flightDepthValue').textContent = smooth('depth', s.pos[2], dt).toFixed(1);
  $('flightAltitude').textContent = alt == null ? '—' : smooth('alt', alt, dt).toFixed(1);
  $('flightClearance').value = alt ?? 3;
  $('flightClearance').style.accentColor = alt < .5 ? 'var(--danger)' : alt < 1.5 ? 'var(--warn)' : 'var(--go)';
  drawFlightAttitude($('flightADI'), s.euler);
  drawFlightCompass($('tape'), s.euler?.[2] || 0, dt);
  const objective = s.expedition?.active?.steps?.find(item => !item.completed)
    || s.mission?.targets?.find(item => !item.done)
    || s.score?.objectives?.find(item => !item.done);
  $('flightMission').textContent = (objective?.label || objective?.name || $('scoreState').textContent)
    + (objective?.progress != null ? ` · ${Math.round(objective.progress * 100)}%` : '');
  if (!$('flightCable')) {
    document.querySelector('.readout').insertAdjacentHTML('beforeend',
      `<span>${STRINGS.cable}<b id="flightCable"></b></span>`
      + `<span>${STRINGS.battery}<b id="flightBattery"></b>%</span>`);
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
  $('rSpd').textContent = smooth('speed', s.speed_kn || 0, dt).toFixed(2);
  $('flightCable').textContent = `${smooth('cable', s.tether?.length || 0, dt).toFixed(1)} m`;
  $('flightCable').style.color = s.tether?.warn ? 'var(--warn)' : 'var(--text)';
  $('flightBattery').textContent = smooth('battery', s.battery ?? 0, dt).toFixed(0);
  showAssist(s);
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
      : s.battery < 20 ? STRINGS.lowBattery : '';
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
  const index = active < 0 ? 1 : active;
  card.querySelector('strong').textContent = STRINGS.cards[index];
  const sources = [
    ['brief', 'objs', 'missionStatus'], ['thrBars', 'tState', 'tRov', 'gBat', 'damage'], ['activeRoomName'], [],
  ];
  card.querySelector('p').textContent = index === 3
    ? keyCardText(input.bindings)
    : sources[index].map(id => $(id)?.textContent || '').join('\n');
  if (index === 1) {
    const thrusters = Array.from($('thrBars').children).map(function thrusterRow(row) {
      return Array.from(row.children).map(el => el.textContent).filter(Boolean).join(' · ');
    });
    card.querySelector('p').textContent = [
      warning, ...thrusters,
      `${STRINGS.cable} ${$('flightCable').textContent} · ${$('tRov').textContent}`,
      `${STRINGS.battery} ${$('flightBattery').textContent}%`, $('damage').textContent,
    ].filter(Boolean).join('\n');
  }
  if (index === 0 && s.mission?.targets?.length) {
    card.querySelector('p').textContent = document.querySelector('.mission-mode-targets')?.textContent || '';
  }
  card.querySelector('canvas').hidden = index !== 2;
  if (index === 2) drawMap(card.querySelector('canvas'), s, w);
  drawMap($('flightMap'), s, w);
}
