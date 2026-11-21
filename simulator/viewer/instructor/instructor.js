/* Independent authenticated console: telemetry, injection lifecycle and server-owned assessment evidence. */
import {STRINGS as S, PHASES, METRICS} from './strings.js';
import {createMap} from './map.js';
import {buildDebriefHtml, downloadDebriefHtml} from '../debrief/report.js';
import {STRINGS as DEBRIEF_S} from '../debrief/strings.js';
import {extractEventsFromFrames} from '../debrief/events.js';
import {createStateMerger, VIEWER_CAPS} from '../state_merge.js';
const root = document.querySelector('#app');
let socket;
let authenticated = false;
let lastStateAt = 0;
let state = {};
const stateMerger = createStateMerger();
let report;
let pending = false;
let reportPending = false;
const actionButtons = [];
const exportButtons = [];
const cards = new Map();
function el(tag, text, parent = root, className = '') {
  const node = document.createElement(tag);
  node.textContent = text || '';
  node.className = className;
  parent.append(node);
  return node;
}
function button(key, handler, parent, gated = true) {
  const node = el('button', S[key], parent);
  node.type = 'button';
  node.addEventListener('click', handler);
  if (gated) actionButtons.push(node);
  return node;
}
function field(key, value, parent, type = 'number', min, max, step = 'any') {
  const input = el('input', '', el('label', S[key], parent));
  input.type = type;
  input.value = value;
  if (min !== undefined) input.min = min;
  if (max !== undefined) input.max = max;
  input.step = step;
  input.id = key;
  return input;
}
function select(key, values, parent) {
  const input = el('select', '', el('label', S[key], parent));
  input.id = key;
  for (const value of values) el('option', S[value] || value, input).value = value;
  return input;
}
function section(key, parent, className = '') {
  const node = el('section', '', parent, className);
  el('h2', S[key], node);
  return node;
}
function numeric(value, digits = 1) {
  return Number.isFinite(value) ? value.toFixed(digits) : S.missing;
}
function live() {
  return authenticated && socket?.readyState === WebSocket.OPEN && Date.now() - lastStateAt < 5000;
}
function updateAvailability() {
  for (const node of actionButtons) node.disabled = !live() || !target.value || pending;
  for (const node of document.querySelectorAll('.active-event button')) node.disabled = !live() || pending;
  for (const node of exportButtons) node.disabled = !live() || !report || report.vehicle_id !== target.value;
}
function command(action, extra = {}) {
  if (!live() || pending || !target.value) return;
  pending = true;
  socket.send(JSON.stringify({type: 'instructor', action, vehicle_id: target.value, ...extra}));
  updateAvailability();
}
function refreshReport() {
  if (!live() || reportPending || !target.value) return;
  reportPending = true;
  socket.send(JSON.stringify({type: 'instructor', action: 'report', vehicle_id: target.value}));
}
function download(name, content, type) {
  if (!report || report.vehicle_id !== target.value) return;
  const url = URL.createObjectURL(new Blob([content], {type}));
  const link = el('a');
  link.href = url;
  link.download = `${report.vehicle_id}-${name}`;
  link.click();
  link.remove();
  setTimeout(function revoke() { URL.revokeObjectURL(url); }, 1000);
}
const header = el('header');
el('div', S.subtitle, header, 'eyebrow');
const titleRow = el('div', '', header, 'title-row');
el('h1', S.title, titleRow);
const status = el('output', S.offline, titleRow);
status.setAttribute('aria-live', 'polite');
const login = el('form', '', header, 'login');
const room = field('room', 'training', login, 'text');
const code = field('code', '', login, 'password');
code.autocomplete = 'off';
code.required = true;
const connect = button('connect', function noop() {}, login, false);
connect.type = 'submit';
login.addEventListener('submit', function join(event) {
  event.preventDefault();
  socket?.close();
  authenticated = false;
  pending = false;
  reportPending = false;
  report = null;
  state = {};
  stateMerger.reset();
  cards.clear();
  fleet.replaceChildren();
  target.replaceChildren();
  chart.reset();
  renderReport();
  active.replaceChildren();
  timeline.replaceChildren();
  const secret = code.value;
  code.value = '';
  const port = new URLSearchParams(location.search).get('ws_port') || 8765;
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  const connection = new WebSocket(`${scheme}://${location.hostname}:${port}`);
  socket = connection;
  status.textContent = S.connecting;
  updateAvailability();
  connection.onopen = function authenticate() {
    if (socket !== connection) return;
    connection.send(JSON.stringify({
      type: 'instructor_join', room_id: room.value.trim(), code: secret, caps: VIEWER_CAPS,
    }));
  };
  connection.onmessage = function message(event) {
    if (socket === connection) receive(JSON.parse(event.data));
  };
  connection.onclose = function close() {
    if (socket !== connection) return;
    authenticated = false;
    status.textContent = S.offline;
    root.classList.add('stale');
    updateAvailability();
  };
  connection.onerror = function error() {
    if (socket === connection) status.textContent = S.offline;
  };
});
const dashboard = el('div', '', root, 'dashboard');
const fleetPanel = section('fleet', dashboard, 'fleet-panel');
const fleet = el('div', S.emptyFleet, fleetPanel);
fleet.id = 'fleet';
const mapPanel = section('map', dashboard, 'map-panel');
const mapToolbar = el('div', '', mapPanel, 'map-toolbar');
el('span', S.mapHelp, mapToolbar);
button('zoomOut', function zoomOut() { chart.zoom(1 / 1.3); }, mapToolbar, false);
button('zoomIn', function zoomIn() { chart.zoom(1.3); }, mapToolbar, false);
button('fit', function fit() { chart.fit(); }, mapToolbar, false);
const canvas = el('canvas', '', mapPanel);
canvas.setAttribute('aria-label', S.map);
const chart = createMap(canvas);
el('p', S.legend, mapPanel, 'legend');
const faults = section('faults', dashboard, 'fault-panel');
const target = select('target', [], faults);
target.addEventListener('change', function selection() {
  report = null;
  renderReport();
  renderFleet();
  updateAvailability();
  refreshReport();
});
const injection = el('form', '', faults, 'injection');
const kind = select('kind', ['thruster', 'battery', 'current', 'visibility', 'freeze', 'tether_snag',
  'video_delay', 'video_freeze',
  'link_degrade', 'comms_loss', 'power_trip', 'leak', 'overheat',
  'compass', 'depth_sensor', 'dvl', 'altimeter'], injection);
el('h3', S.drills, faults);
const drills = el('div', '', faults, 'training-drills');
const DRILL_PRESETS = [
  {key: 'drillCurrent', kind: 'current', strength: 0.6, duration: 90, ramp_s: 60, rotate_deg: 0},
  {key: 'drillVisibility', kind: 'visibility', strength: 0.5, duration: 45},
  {key: 'drillCompass', kind: 'compass', strength: 0.4, duration: 45},
  {key: 'drillSnag', kind: 'tether_snag', strength: 0.5, duration: 120},
];
for (const preset of DRILL_PRESETS) {
  button(preset.key, function fireDrill() {
    const payload = {kind: preset.kind, strength: preset.strength, duration: preset.duration};
    if (preset.kind === 'current') {
      payload.ramp_s = preset.ramp_s;
      payload.rotate_deg = preset.rotate_deg;
    }
    if (preset.kind === 'thruster') payload.index = 0;
    command('inject', payload);
  }, drills);
}
const inputs = el('div', '', injection, 'fields');
const strength = field('strength', '.5', inputs, 'number', 0, 1, .05);
const duration = field('duration', '30', inputs, 'number', .1, 3600);
const index = field('index', '0', inputs, 'number', 0, 7, 1);
const ramp = field('ramp_s', '60', inputs, 'number', 30, 120, 1);
const rotate = field('rotate_deg', '0', inputs, 'number', -180, 180, 1);
for (const input of [strength, duration, index]) input.required = true;
function syncInjectionFields() {
  index.disabled = kind.value !== 'thruster';
  const current = kind.value === 'current';
  for (const input of [ramp, rotate]) {
    input.disabled = !current;
    input.required = current;
    input.closest('label')?.toggleAttribute('hidden', !current);
  }
  duration.disabled = false;
}
kind.addEventListener('change', syncInjectionFields);
syncInjectionFields();
const inject = button('inject', function noop() {}, injection);
inject.type = 'submit';
injection.addEventListener('submit', function submit(event) {
  event.preventDefault();
  const payload = {kind: kind.value, strength: +strength.value, duration: +duration.value, index: +index.value};
  if (kind.value === 'current') {
    payload.ramp_s = +ramp.value;
    payload.rotate_deg = +rotate.value;
  }
  command('inject', payload);
});
el('h3', S.active, faults);
const active = el('div', S.emptyActive, faults, 'active-events');
el('h3', S.timeline, faults);
const timeline = el('ol', S.emptyEvents, faults, 'timeline');
const bottom = section('assessment', root, 'assessment');
const assessmentToolbar = el('div', '', bottom, 'assessment-toolbar');
const flow = select('flow', ['flow', 'still'], assessmentToolbar);
flow.setAttribute('aria-label', `${S.flow} / ${S.still}`);
flow.addEventListener('change', renderReport);
const reportClock = el('span', '', assessmentToolbar, 'mono');
button('report', refreshReport, assessmentToolbar);
exportButtons.push(button('json', function json() {
  download('training.json', JSON.stringify(report, null, 2), 'application/json');
}, assessmentToolbar, false));
exportButtons.push(button('csv', function csv() {
  const rows = report.trajectory || [];
  const content = ['t,phase,north,east,depth', ...rows.map(r => [r.t, r.phase, ...r.pos].join(','))].join('\n');
  download('trajectory.csv', content, 'text/csv');
}, assessmentToolbar, false));
exportButtons.push(button('html', function html() {
  const events = [];
  for (const item of report.events || []) {
    if (item.restored_at !== undefined || item.kind === 'control_response') continue;
    events.push({kind: 'instructor_inject', t: item.start ?? item.injection_start ?? 0,
      detail: String(item.kind || '')});
  }
  for (const contact of report.collisions || []) {
    events.push({kind: 'collision', t: contact.t || 0,
      detail: [contact.obstacle, contact.severity].filter(Boolean).join(' · ')});
  }
  for (const penalty of report.completion?.penalties || []) {
    events.push({kind: 'penalty', t: penalty.t || 0, detail: penalty.reason || ''});
  }
  // Trajectory frames are sparse; reuse the shared extractor shape for objective edges when present.
  const frames = (report.trajectory || []).map(function asFrame(sample) {
    return {t: sample.t, events: sample.collisions || [], tether: {wraps: sample.wraps || {}},
      score: sample.completion || report.completion || {}, silt: 0};
  });
  events.push(...extractEventsFromFrames(frames).filter(function onlyObjectives(row) {
    return row.kind === 'objective_done' || row.kind === 'tether_snag';
  }));
  events.sort(function byTime(a, b) { return a.t - b.t; });
  const page = buildDebriefHtml({report, events, notes: '', strings: {...DEBRIEF_S, title: S.title}});
  downloadDebriefHtml(`${report.vehicle_id}-debrief.html`, page);
}, assessmentToolbar, false));
const matrix = el('div', '', bottom, 'matrix');
el('p', S.provisional, bottom, 'legend');
const settings = el('div', '', root, 'settings');
const reference = el('details', '', settings);
el('summary', S.reference, reference);
const referenceForm = el('form', '', reference, 'reference-form');
const phase = select('phase', PHASES, referenceForm);
const north = field('targetNorth', '0', referenceForm);
const east = field('targetEast', '0', referenceForm);
const depth = field('targetDepth', '5', referenceForm);
const heading = field('targetHeading', '0', referenceForm);
for (const input of [north, east, depth, heading]) input.required = true;
const apply = button('apply', function noop() {}, referenceForm);
apply.type = 'submit';
referenceForm.addEventListener('submit', function applyReference(event) {
  event.preventDefault();
  command('reference', {phase: phase.value, reference: {
    target: [+north.value, +east.value, +depth.value], depth: +depth.value, heading: +heading.value,
  }});
});
const controls = el('details', '', settings);
el('summary', S.controls, controls);
button('pause', function pause() { command('pause', {value: true}); }, controls);
button('resume', function resume() { command('pause', {value: false}); }, controls);
button('return', function returnVehicle() {
  if (window.confirm(S.confirmReturn)) command('return');
}, controls);
button('reset', function reset() {
  if (window.confirm(S.confirmReset)) command('reset');
}, controls);
function renderFleet() {
  const vehicles = state.vehicles || [];
  const players = state.room?.players || [];
  if (!cards.size) fleet.replaceChildren();
  for (const v of vehicles) {
    let card = cards.get(v.id);
    if (!card) {
      card = el('article', '', fleet, 'student');
      card.tabIndex = 0;
      card.setAttribute('role', 'button');
      card.addEventListener('click', function choose() {
        target.value = v.id;
        target.dispatchEvent(new Event('change'));
      });
      card.addEventListener('keydown', function chooseKey(event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          card.click();
        }
      });
      cards.set(v.id, card);
    }
    card.replaceChildren();
    const health = v.health || [];
    const severity = v.tether?.broken || health.some(h => h <= 0) || v.score?.failed ? 'danger'
      : v.tether?.warn || health.some(h => h < 1) || v.battery < 20 ? 'caution' : 'normal';
    card.className = `student ${severity} ${v.id === target.value ? 'selected' : ''}`;
    card.setAttribute('aria-pressed', String(v.id === target.value));
    const player = players.find(p => p.vehicle_id === v.id);
    const cardHead = el('div', '', card, 'card-head');
    el('h3', `${v.id} / ${player?.name || v.id}`, cardHead);
    el('span', S[severity], cardHead, severity);
    el('p', `${v.locked ? S.locked : S.unlocked}${v.paused ? ` · ${S.paused}` : ''}`
      + (player?.connected === false ? ` · ${S.disconnected}` : ''), card, 'lock-state');
    const readings = el('div', '', card, 'readings');
    for (const [label, value, unit] of [[S.depth, v.pos?.[2], S.metres], [S.speed, v.speed_kn, S.knots]]) {
      const reading = el('div', '', readings);
      el('span', label, reading, 'label');
      el('strong', numeric(value), reading);
      el('small', unit, reading);
    }
    el('p', S.attitude, card, 'label');
    el('div', (v.euler || []).map(n => `${numeric(n)}°`).join(' / '), card, 'mono attitude');
    el('p', S.tether, card, 'label');
    el('div', `${numeric(v.tether?.length)} ${S.metres} / ${numeric(v.tether?.tension_rov)} ${S.newtons}`,
      card, 'mono');
    const healthRow = el('div', '', card, 'health');
    el('span', S.health, healthRow, 'label');
    health.forEach(function thruster(h, i) {
      const meter = el('span', `${i + 1}`, healthRow, h < 1 ? 'caution' : 'normal');
      meter.title = `${S.health} ${i}: ${Math.round(h * 100)}%`;
      meter.setAttribute('aria-label', meter.title);
      meter.style.setProperty('--health-value', h);
    });
    const score = v.score || {};
    const objective = score.objectives?.[score.current_index];
    const task = score.failed ? S.failed : score.finished ? S.complete : objective?.label || v.mission?.label || S.idle;
    const progress = objective ? `${score.current_index + 1}/${score.objectives.length} · ` : '';
    el('p', `${S.task} · ${progress}${task}`, card, 'task');
  }
  for (const [id, card] of cards) {
    if (!vehicles.some(v => v.id === id)) {
      card.remove();
      cards.delete(id);
    }
  }
  if (!vehicles.length) fleet.textContent = S.emptyFleet;
  chart.update(vehicles, target.value);
}
function renderReport() {
  matrix.replaceChildren();
  reportClock.textContent = report
    ? `${S.reportTime} ${numeric(report.elapsed)} ${S.seconds} / ${report.vehicle_id}` : S.noReport;
  for (const key of PHASES) {
    const column = el('div', '', matrix, 'phase');
    el('h3', S[key], column);
    for (const metric of METRICS) {
      const result = report?.matrix?.[key]?.[flow.value === 'flow' ? 'current' : 'still']?.[metric];
      const row = el('div', '', column, `grade ${result?.grade || 'ungraded'}`);
      el('span', metric === 'speed' ? S.speedError : S[metric], row);
      el('span', result ? S[result.grade] : S.ungraded, row);
      if (result) row.title = `${S.metricHelp}: ${numeric(result.rms)} / ${numeric(result.min)} / `
        + `${numeric(result.max)} / ${numeric(result.outside_fraction * 100)}%`;
    }
  }
}
function renderEvents() {
  active.replaceChildren();
  const events = report?.supervision?.active;
  if (!events) active.textContent = S.legacy;
  else if (!events.length) active.textContent = S.emptyActive;
  for (const event of events || []) {
    const row = el('div', '', active, 'active-event');
    el('span', `${S[event.kind]} · ${event.scope === 'room' ? S.roomScope : event.vehicle_id}`, row);
    el('strong', `${Math.max(0, Math.ceil(event.end - report.elapsed))} ${S.seconds}`, row, 'mono');
    const stop = button('end', function stopEvent() {
      command('inject', {vehicle_id: event.vehicle_id, kind: event.kind, cancel_start: event.start});
    }, row, false);
    stop.disabled = !live() || pending;
  }
  timeline.replaceChildren();
  for (const event of (report?.events || []).slice(-40).reverse()) {
    const time = event.restored_at ?? event.start ?? event.injection_start;
    const row = el('li', '', timeline);
    el('time', `${numeric(time)} ${S.seconds}`, row, 'mono');
    el('span', `${S[event.kind] || event.kind} · ${event.vehicle_id}`
      + (event.restored_at !== undefined ? ` · ${S.restored}` : ''), row);
  }
  if (!timeline.children.length) timeline.textContent = S.emptyEvents;
}
function receive(message) {
  if (message.type === 'instructor_session') {
    authenticated = true;
    status.textContent = S.connected;
  }
  if (message.type === 'world' && authenticated) chart.world(message);
  if (message.type === 'error') {
    pending = false;
    reportPending = false;
    status.textContent = `${S.rejected}: ${message.message || message.code}`;
    updateAvailability();
  }
  if (message.type === 'instructor_result') {
    pending = false;
    status.textContent = S.success;
    if (message.action === 'reset') {
      chart.reset();
      report = null;
      renderReport();
    }
    refreshReport();
    updateAvailability();
  }
  if (message.type === 'training_report') {
    reportPending = false;
    if (message.report.vehicle_id === target.value) {
      report = message.report;
      if (report.supervision?.world) chart.world(report.supervision.world);
      renderReport();
      renderEvents();
    } else refreshReport();
    updateAvailability();
  }
  if (message.type === 'state') message = stateMerger.merge(message);
  if (message.type !== 'state' || !authenticated) return;
  state = message;
  lastStateAt = Date.now();
  root.classList.remove('stale');
  const vehicles = state.vehicles || [];
  const ids = vehicles.map(v => v.id);
  if (ids.join(',') !== [...target.options].map(o => o.value).join(',')) {
    const selected = target.value;
    target.replaceChildren();
    for (const v of vehicles) el('option', v.id, target).value = v.id;
    if (ids.includes(selected)) target.value = selected;
    else {
      report = null;
      renderReport();
    }
  }
  const vehicle = vehicles.find(v => v.id === target.value);
  index.max = Math.max(0, (vehicle?.health?.length || 1) - 1);
  renderFleet();
  updateAvailability();
}
setInterval(function poll() {
  if (authenticated && !live()) {
    status.textContent = S.stale;
    root.classList.add('stale');
  }
  updateAvailability();
  refreshReport();
}, 2000);
renderReport();
updateAvailability();
