// Multiplayer screen: player name, server address and room code, create or join, and who is in the room.
// The room list comes from the optional read-only `room_query` message (PROTOCOL.md); the menu only opens a
// connection while this screen is shown, and never joins: joining happens when the game starts.
import { normaliseServer, validRoom } from './preferences.js';
import { field } from './settings.js';

const STRINGS = {
  title: '多人',
  name: '操作員名稱',
  room: '房間代碼',
  server: '伺服器',
  serverHelp: '單人遊玩保留本機位址即可；多人請填同一台主機與相同房間代碼。',
  create: '建立新房間',
  join: '加入房間',
  refresh: '重新整理',
  players: '房內玩家',
  checking: '正在查詢房間…',
  empty: '房間尚未建立；第一位進入的人成為房主。',
  full: '房間已滿（{n}/{n}）。',
  count: '{count}/{capacity} 人 · 房主決定場景與玩法',
  host: '房主',
  away: '暫離',
  unsupported: '此伺服器不提供房間查詢；仍可直接加入。',
  offline: '無法連到伺服器，請確認位址。',
  createHint: '建立後把房間代碼告訴隊友。',
};
const QUERY_TIMEOUT_MS = 10000;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function input(value, options = {}) {
  const node = element('input');
  node.value = value;
  node.spellcheck = false;
  Object.assign(node, options);
  return node;
}

export function newRoomCode(random = Math.random) {
  const letters = 'abcdefghjkmnpqrstuvwxyz23456789';
  let code = 'dive-';
  for (let index = 0; index < 4; index++) code += letters[Math.floor(random() * letters.length)];
  return code;
}

// Resolves with the server's room_info reply, or rejects with a user-facing message.
export function queryRoom(server, room) {
  return new Promise(function query(resolve, reject) {
    let socket;
    try {
      socket = new WebSocket(server);
    } catch {
      reject(new Error(STRINGS.offline));
      return;
    }
    const timer = setTimeout(function giveUp() {
      socket.close();
      reject(new Error(STRINGS.offline));
    }, QUERY_TIMEOUT_MS);
    function finish() {
      clearTimeout(timer);
      socket.close();
    }
    socket.addEventListener('open', function ask() {
      socket.send(JSON.stringify({ type: 'room_query', room_id: room }));
    });
    socket.addEventListener('message', function answer(event) {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (message.type === 'room_info') {
        finish();
        resolve(message);
      } else if (message.type === 'error') {
        finish();
        reject(new Error(STRINGS.unsupported));
      }
    });
    socket.addEventListener('error', function failed() {
      clearTimeout(timer);
      reject(new Error(STRINGS.offline));
    });
  });
}

export function buildMultiplayer(ctx) {
  const root = element('section', 'menu-screen');
  root.dataset.screen = 'multiplayer';
  root.setAttribute('aria-label', STRINGS.title);
  root.append(element('h2', 'menu-heading', STRINGS.title));
  const layout = element('div', 'menu-columns');
  const form = element('div', 'menu-form');
  const name = input(ctx.choice.name, { maxLength: 32 });
  const room = input(ctx.choice.room, { maxLength: 32, pattern: '[A-Za-z0-9_-]{1,32}' });
  const server = input(ctx.choice.server, { type: 'url' });
  field(form, { id: 'menuName', label: STRINGS.name, control: name });
  field(form, { id: 'menuRoom', label: STRINGS.room, control: room });
  field(form, { id: 'menuServer', label: STRINGS.server, help: STRINGS.serverHelp, control: server });
  const actions = element('div', 'menu-actions');
  const create = element('button', 'menu-next', STRINGS.create);
  create.type = 'button';
  create.id = 'mpCreate';
  const join = element('button', 'menu-next', STRINGS.join);
  join.type = 'button';
  join.id = 'mpJoin';
  join.dataset.autofocus = '';
  actions.append(join, create);
  form.append(actions);
  const roster = element('section', 'menu-roster');
  const rosterHead = element('div', 'menu-roster-head');
  const refresh = element('button', 'menu-chip menu-chip-small', STRINGS.refresh);
  refresh.type = 'button';
  refresh.id = 'mpRefresh';
  rosterHead.append(element('h3', 'menu-label', STRINGS.players), refresh);
  const status = element('p', 'menu-help');
  status.id = 'mpStatus';
  status.setAttribute('role', 'status');
  const players = element('ul', 'menu-players');
  players.id = 'mpPlayers';
  roster.append(rosterHead, status, players);
  layout.append(form, roster);
  root.append(layout);
  let ticket = 0;
  let timer = 0;
  function read() {
    ctx.choice.name = name.value.trim() || ctx.choice.name;
    ctx.choice.room = validRoom(room.value.trim());
    ctx.choice.server = normaliseServer(server.value, location.protocol);
  }
  function showPlayers(info) {
    players.replaceChildren();
    if (!info.exists || !info.players.length) {
      status.textContent = STRINGS.empty;
      return;
    }
    const count = info.players.length;
    status.textContent = count >= info.capacity
      ? STRINGS.full.replaceAll('{n}', String(info.capacity))
      : STRINGS.count.replace('{count}', String(count)).replace('{capacity}', String(info.capacity));
    for (const player of info.players) {
      const item = element('li');
      item.append(element('strong', '', player.name));
      const vehicle = ctx.data.vehicles.find(function byId(entry) {
        return entry.id === player.model_id;
      });
      item.append(element('span', '', vehicle?.name || player.model_id));
      if (player.host) item.append(element('span', 'menu-tag', STRINGS.host));
      if (!player.connected) item.append(element('span', 'menu-tag', STRINGS.away));
      players.append(item);
    }
  }
  async function refreshRoster() {
    const current = ++ticket;
    try {
      read();
    } catch (error) {
      status.textContent = error.message;
      return;
    }
    status.textContent = STRINGS.checking;
    try {
      const info = await queryRoom(ctx.choice.server, ctx.choice.room);
      if (current === ticket) showPlayers(info);
    } catch (error) {
      if (current !== ticket) return;
      players.replaceChildren();
      status.textContent = error.message;
    }
  }
  function later() {
    clearTimeout(timer);
    timer = setTimeout(refreshRoster, 600);
  }
  room.addEventListener('input', later);
  server.addEventListener('change', later);
  name.addEventListener('change', function rename() {
    ctx.choice.name = name.value.trim() || ctx.choice.name;
  });
  refresh.addEventListener('click', refreshRoster);
  function proceed(joining) {
    try {
      read();
    } catch (error) {
      ctx.setStatus(error.message);
      return;
    }
    ctx.choice.joining = joining;
    ctx.startRoute(joining ? 'join' : 'dive');
  }
  join.addEventListener('click', function joinRoom() {
    proceed(true);
  });
  create.addEventListener('click', function createRoom() {
    room.value = newRoomCode();
    ctx.setStatus(STRINGS.createHint);
    proceed(false);
  });
  function enter() {
    name.value = ctx.choice.name;
    room.value = ctx.choice.room;
    server.value = ctx.choice.server;
    refreshRoster();
  }
  function leave() {
    ticket++;
    clearTimeout(timer);
  }
  return { element: root, pose: 'multiplayer', enter, leave };
}
