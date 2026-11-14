/* Independent instructor connection and printable evidence export; never persists credentials. */
const STRINGS = {
  title: '教官台 · 訓練監督', room: '房間', code: '教官碼', connect: '連線', target: '學員載具',
  kind: '物理覆蓋', strength: '強度 0–1', duration: '持續秒數', index: '推進器索引', inject: '注入',
  thruster: '推進器推力下降', battery: '電量下降', current: '全房洋流突變', visibility: '全房能見度下降',
  freeze: '凍結載具', report: '取得報告', pause: '暫停全房', resume: '繼續', reset: '重置並封存報告',
  return: '移回起點', provisional: '評分門檻：暫定；未取樣階段不評級', connected: '已通過教官驗證',
  offline: '連線中斷', html: '下載可列印 HTML', print: '列印 HTML', json: '下載 JSON', csv: '下載軌跡 CSV',
  telemetry: '姿態 / 推進器 / 纜線', phase: '考核階段', reference: '套用考核參考值',
  descent: '下潛', transit: '轉場', hover: '懸停', orbit: '繞行', dock: '對接',
  heading: '目標航向 °', depth: '目標深度 m', north: '目標北向 m', east: '目標東向 m',
};
const root = document.querySelector('#app');
let socket;
let latestReport;
function element(tag, text, parent = root) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  parent.append(node);
  return node;
}
function field(key, value, parent, type = 'text') {
  const label = element('label', STRINGS[key], parent);
  const input = element('input', '', label);
  input.type = type;
  input.value = value;
  return input;
}
function button(key, handler, parent) {
  const node = element('button', STRINGS[key], parent);
  node.onclick = handler;
  return node;
}
function send(message) {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message));
  }
}
function command(action, extra = {}) {
  send({type: 'instructor', action, vehicle_id: target.value, ...extra});
}
function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const link = element('a');
  link.href = url;
  link.download = name;
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
element('h1', STRINGS.title);
const status = element('output', STRINGS.provisional);
const login = element('section');
login.id = 'login';
const room = field('room', 'training', login);
const code = field('code', '', login, 'password');
code.autocomplete = 'off';
button('connect', function connect() {
  socket?.close();
  const port = new URLSearchParams(location.search).get("ws_port") || 8765;
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  socket = new WebSocket(`${scheme}://${location.hostname}:${port}`);
  socket.onopen = function authenticate() {
    send({type: 'instructor_join', room_id: room.value, code: code.value});
    code.value = '';
  };
  socket.onclose = function disconnected() {
    status.textContent = STRINGS.offline;
  };
  socket.onmessage = receive;
}, login);
const commands = element('section');
commands.id = 'commands';
const target = element('select', '', element('label', STRINGS.target, commands));
const kind = element('select', '', element('label', STRINGS.kind, commands));
for (const key of ['thruster', 'battery', 'current', 'visibility', 'freeze']) {
  element('option', STRINGS[key], kind).value = key;
}
const strength = field('strength', '.5', commands, 'number');
const duration = field('duration', '10', commands, 'number');
const index = field('index', '0', commands, 'number');
button('inject', function inject() {
  command('inject', {kind: kind.value, strength: +strength.value, duration: +duration.value, index: +index.value});
}, commands);
for (const action of ['reset', 'return', 'report']) button(action, () => command(action), commands);
button('pause', () => command('pause', {value: true}), commands);
button('resume', () => command('pause', {value: false}), commands);
const phase = element('select', '', element('label', STRINGS.phase, commands));
for (const key of ['descent', 'transit', 'hover', 'orbit', 'dock']) {
  element('option', STRINGS[key], phase).value = key;
}
const north = field('north', '0', commands, 'number');
const east = field('east', '0', commands, 'number');
const depth = field('depth', '5', commands, 'number');
const heading = field('heading', '0', commands, 'number');
button('reference', function reference() {
  command('reference', {phase: phase.value, reference: {
    target: [+north.value, +east.value, +depth.value], depth: +depth.value, heading: +heading.value,
  }});
}, commands);
const fleet = element('div');
fleet.id = 'fleet';
const evidence = element('section');
const reportText = element('pre', STRINGS.provisional, evidence);
button('json', () => download('training.json', JSON.stringify(latestReport, null, 2), 'application/json'), evidence);
button('csv', function csv() {
  const rows = latestReport?.trajectory || [];
  const data = ['t,phase,north,east,depth', ...rows.map(s => [s.t, s.phase, ...s.pos].join(','))].join('\n');
  download('trajectory.csv', data, 'text/csv');
}, evidence);
button('html', function html() {
  const text = JSON.stringify(latestReport, null, 2).replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  const content = '<!doctype html><html lang="zh-Hant"><meta charset="utf-8">'
    + `<title>${STRINGS.title}</title><h1>${STRINGS.title}</h1>`
    + `<p>${STRINGS.provisional}</p><pre style="white-space:pre-wrap">${text}</pre></html>`;
  download('training.html', content, 'text/html');
}, evidence);
button('print', () => window.print(), evidence);
function receive(event) {
  const message = JSON.parse(event.data);
  if (message.type === 'instructor_session') status.textContent = STRINGS.connected;
  if (message.type === 'error') status.textContent = message.message;
  if (message.type === 'instructor_result') status.textContent = `${message.action}: ${message.ok}`;
  if (message.type === 'training_report') {
    latestReport = message.report;
    reportText.textContent = JSON.stringify(message, null, 2);
  }
  if (message.type !== 'state') return;
  const selected = target.value;
  target.replaceChildren();
  fleet.replaceChildren();
  for (const state of message.vehicles || []) {
    element('option', state.id, target).value = state.id;
    const card = element('article', '', fleet);
    element('h2', state.id, card);
    element('p', STRINGS.telemetry, card);
    element('pre', JSON.stringify({pos: state.pos, euler: state.euler, health: state.health,
      thrust: state.thrust, battery: state.battery, tether: {
        length: state.tether.length, tension: state.tether.tension_rov,
        broken: state.tether.broken, wraps: state.tether.wraps,
      }}, null, 2), card);
  }
  if ([...target.options].some(o => o.value === selected)) target.value = selected;
}
