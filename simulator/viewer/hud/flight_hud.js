// Full flight presentation and nonblocking peek cards; never sends vehicle controls.
import { drawFlightCompass } from './compass.js';
import { forwardRange } from './range.js';
import { drawFlightAttitude } from './attitude.js';
const STRINGS = {
  close: '收起工程面板', depth: '深度', altitude: '離底', engineering: '工程 Tab', density: ['極簡', '標準', '完整'],
  hide: '切換 HUD', north: '北朝上', head: '機頭朝上',
  cards: ['任務與目標', '載具系統', '地圖與隊友', '鍵位提示'],
  keys: 'WASD / 方向鍵 飛行\nSpace 鎖定 · H 定深 · L 燈光\n1–4 速覽 · Tab 工程',
  cable: '纜線', battery: '電量',
  danger: '危險：纜線斷裂', warn: '注意：纜線張力', near: '注意：接近海床',
  lowBattery: '提示：電量偏低', forward: '前方估距', controller: 'USB 控制器已連線',
  assist: ['手動', '速度輔助', '定點輔助'],
};
const $ = id => document.getElementById(id);
let ready = false;
let active = -1;
let deadline = 0;
let pressedAt = 0;
let held = false;
let previous = [];
let lastWarning = '';
let viewStarted = null;
let viewToggled = false;
let north = true;
let density = 1;
const values = {};
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
function up() {
  if (held && performance.now() - pressedAt > 250) active = -1;
  held = false;
}
// Standard D-pad adapter, isolated for replacement by the shared input module.
export function readHUDButtons() {
  const pad = Array.from(navigator.getGamepads?.() || []).find(p => p?.mapping === 'standard');
  return [12, 14, 15, 13].map(index => !!pad?.buttons[index]?.pressed);
}
function setDensity() {
  document.body.classList.toggle('hud-minimal', density === 0);
  $('flightDensity').textContent = STRINGS.density[density];
  save('rov.hud.density', String(density));
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
  $('flightDrawer').onclick = drawer;
  $('flightMapMode').onclick = function toggleNorth() {
    north = !north;
    this.textContent = north ? STRINGS.north : STRINGS.head;
  };
  density = Number(storage('rov.hud.density', '1'));
  setDensity();
  $('flightDensity').onclick = function cycleDensity() {
    density = (density + 1) % 3;
    setDensity();
  };
  $('flightHide').onclick = function hideHUD() { document.body.classList.toggle('hud-hidden'); };
  document.addEventListener('keydown', function keyDown(event) {
    if (event.target.closest('input,select,textarea,[contenteditable=true]')) return;
    document.body.classList.remove('hud-touch');
    if (event.code === 'Tab') {
      event.preventDefault();
      if (!event.repeat) drawer();
    }
    const index = ['Digit1', 'Digit2', 'Digit3', 'Digit4'].indexOf(event.code);
    if (index >= 0 && !event.repeat) down(index);
  });
  document.addEventListener('keyup', function keyUp(event) {
    if (['Digit1', 'Digit2', 'Digit3', 'Digit4'].includes(event.code)) up();
  });
  window.addEventListener('blur', function blur() {
    held = false;
    active = -1;
  });
  document.addEventListener('pointerdown', function pointer(event) {
    document.body.classList.toggle('hud-touch', event.pointerType === 'touch');
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
      ctx.strokeRect(x - 5, y - 5, 10, 10);
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
    if (!peer.pos || peer.vehicle_id === s.vehicle_id) continue;
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
export function updateFlightHUD(s, w, dt) {
  if (!ready) initialize();
  if (!s?.pos) return;
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
    document.querySelector('.chips').append(chip);
  }
  $('rSpd').textContent = smooth('speed', s.speed_kn || 0, dt).toFixed(2);
  $('flightCable').textContent = `${smooth('cable', s.tether?.length || 0, dt).toFixed(1)} m`;
  $('flightCable').style.color = s.tether?.warn ? 'var(--warn)' : 'var(--text)';
  $('flightBattery').textContent = smooth('battery', s.battery ?? 0, dt).toFixed(0);
  $('flightAssist').hidden = !s.assist;
  if (s.assist) $('flightAssist').textContent = `${STRINGS.assist[s.assist.level]} · ${s.assist.profile}`;
  const warning = s.tether?.broken ? STRINGS.danger : s.tether?.warn ? STRINGS.warn
    : alt != null && alt < 1 || range != null && range < 1 ? STRINGS.near
      : s.battery < 20 ? STRINGS.lowBattery : '';
  $('flightWarning').textContent = warning;
  $('flightWarning').dataset.level = s.tether?.broken ? 'danger'
    : warning === STRINGS.lowBattery ? 'info' : 'warning';
  document.body.classList.toggle('hud-danger', !!s.tether?.broken);
  if (warning && warning !== lastWarning) {
    active = 1;
    deadline = performance.now() + 3000;
    const pad = Array.from(navigator.getGamepads?.() || []).find(p => p?.vibrationActuator);
    pad?.vibrationActuator?.playEffect('dual-rumble', {
      duration: 180, strongMagnitude: s.tether?.broken ? .8 : .2, weakMagnitude: .2,
    }).catch(function ignoreUnsupportedRumble() {});
  }
  lastWarning = warning;
  const pad = Array.from(navigator.getGamepads?.() || []).find(p => p?.mapping === 'standard');
  if (pad?.buttons.some(button => button.pressed) || pad?.axes.some(axis => Math.abs(axis) > .15)) {
    document.body.classList.remove('hud-touch');
  }
  if (pad?.buttons[8]?.pressed) {
    viewStarted ??= performance.now();
    if (!viewToggled && performance.now() - viewStarted > 650) {
      drawer();
      viewToggled = true;
    }
  } else {
    viewStarted = null;
    viewToggled = false;
  }
  const buttons = readHUDButtons();
  buttons.forEach(function checkButton(pressed, index) {
    if (pressed && !previous[index]) down(index);
    if (!pressed && previous[index]) up();
  });
  previous = buttons;
  if (buttons.some(Boolean)) document.body.classList.remove('hud-touch');
  if (!held && performance.now() > deadline) active = -1;
  const card = $('flightPeek');
  card.classList.toggle('visible', active >= 0 || density === 2);
  const index = active < 0 ? 1 : active;
  card.querySelector('strong').textContent = STRINGS.cards[index];
  const sources = [
    ['brief', 'objs', 'missionStatus'], ['thrBars', 'tState', 'tRov', 'gBat', 'damage'], ['activeRoomName'], [],
  ];
  card.querySelector('p').textContent = index === 3
    ? ($('pilotGuide')?.querySelector('.pilot-mode')?.textContent || '') + '\n'
      + ($('pilotGuide')?.querySelector('dl')?.textContent || STRINGS.keys)
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
