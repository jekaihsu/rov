// Launch choices: read them from the URL and earlier sessions, remember them, and build the game URL.
// Keeps the storage keys the game and the desktop shell already use (rov.vehicle, rov.mission, rov.sticker,
// rov.quality, rov.playerName, rov.menuSettings, the control layout key) and adds one record for 快速開始.
import { CONTROL_LAYOUTS, controlLayout, rememberControlLayout } from '../control_layout.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('menu.preferences', {
  badServer: '請填寫有效的伺服器位址。',
  needSecure: '安全網頁需要使用 wss:// 伺服器。',
  badRoom: '房間代碼須為 1–32 個英數字、底線或連字號。',
  defaultName: '操作員',
});

export const LAST_KEY = 'rov.menu.last.v1';
export const MODEL_IDS = ['x1', 'bluerov2_heavy', 'falcon'];
export const QUALITY_MODES = ['auto', 'performance', 'medium', 'high'];
const MISSIONS = ['campaign', 'expedition', 'free_explore', 'inspection_coop', 'scenario_training'];
const ROOM_PATTERN = /^[A-Za-z0-9_-]{1,32}$/;
const INTERFACE_DEFAULTS = { pip: false, intro: true, alwaysIntro: false, sticks: true, fog: true, labels: true };
// Set once the launch cinematic has been chosen for a dive; afterwards it is skipped unless alwaysIntro is on.
export const INTRO_SEEN_KEY = 'rov.intro.seen.v1';

function storage() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

function read(key, fallback) {
  try {
    return storage()?.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

function write(key, value) {
  try {
    storage()?.setItem(key, value);
  } catch {
    // Private windows may refuse storage; the URL still carries every choice.
  }
}

function readJson(key) {
  try {
    const value = JSON.parse(read(key, '{}'));
    return value && typeof value === 'object' ? value : {};
  } catch {
    return {};
  }
}

export function defaultServer(location) {
  if (location.protocol === 'https:') return `wss://${location.host}/ws`;
  return `ws://${location.hostname || '127.0.0.1'}:8765`;
}

// Everything the launch flow can choose, with URL parameters taking precedence over stored values.
export function initialChoice(location = globalThis.location) {
  const query = new URLSearchParams(location.search);
  const last = readJson(LAST_KEY);
  const stored = readJson('rov.menuSettings');
  const model = query.get('model') || read('rov.vehicle', last.model || 'x1');
  const mission = query.get('mission') || read('rov.mission', last.mission || 'campaign');
  const quality = query.get('quality') || read('rov.quality', 'auto');
  const requestedControl = query.get('control');
  const choice = {
    model: MODEL_IDS.includes(model) ? model : 'x1',
    mission: MISSIONS.includes(mission) ? mission : 'expedition',
    scenario: query.get('scenario') || query.get('scene') || last.scenario || 'coral_reef',
    chapter: query.get('chapter') || last.chapter || '',
    sticker: query.get('sticker') || read('rov.sticker', 'none'),
    room: query.get('room') || last.room || 'training',
    name: query.get('name') || read('rov.playerName', STRINGS.defaultName),
    server: query.get('ws') || defaultServer(location),
    quality: QUALITY_MODES.includes(quality) ? quality : 'auto',
    control: CONTROL_LAYOUTS.includes(requestedControl) ? requestedControl : controlLayout(),
    pad: query.get('pad') || 'auto',
    joining: false,
  };
  for (const [key, fallback] of Object.entries(INTERFACE_DEFAULTS)) {
    choice[key] = typeof stored[key] === 'boolean' ? stored[key] : fallback;
  }
  // introPreference is the stored 下水動畫 setting; intro is what this launch does (introForLaunch()).
  choice.introPreference = choice.intro;
  choice.introSeen = read(INTRO_SEEN_KEY, '') === '1';
  if (query.has('nointro')) choice.intro = false;
  return choice;
}

// The launch cinematic plays on the first dive; later dives start in the water unless the player keeps it on
// (alwaysIntro). The full pre-dive procedure, which the same switch controls, is never skipped this way.
export function introForLaunch(choice, procedureFull = false) {
  const preferred = !!(choice.introPreference ?? choice.intro);
  if (!preferred) return false;
  if (procedureFull || choice.alwaysIntro) return true;
  return !choice.introSeen;
}

export function hasLastSession() {
  return Object.keys(readJson(LAST_KEY)).length > 0;
}

export function lastSession() {
  return readJson(LAST_KEY);
}

// http(s) addresses are accepted and turned into the matching WebSocket address.
export function normaliseServer(text, pageProtocol = 'http:') {
  let server;
  try {
    server = new URL(String(text).trim());
  } catch {
    throw new Error(STRINGS.badServer);
  }
  if (server.protocol === 'https:' || server.protocol === 'http:') {
    server.protocol = server.protocol === 'https:' ? 'wss:' : 'ws:';
    if (server.pathname === '/') server.pathname = '/ws';
  }
  if (!['ws:', 'wss:'].includes(server.protocol) || server.username || server.password) {
    throw new Error(STRINGS.badServer);
  }
  if (pageProtocol === 'https:' && server.protocol !== 'wss:') throw new Error(STRINGS.needSecure);
  return server.href;
}

export function validRoom(room) {
  if (!ROOM_PATTERN.test(room)) throw new Error(STRINGS.badRoom);
  return room;
}

// A YX contract dive carries ?contract=<id>; an exam also forces the real fidelity preset (?fidelity=real&exam=1)
// and drops the per-item fidelity overrides so nothing beyond the real vehicle leaks into it.
export const EXAM_CLEARED_PARAMS = ['cam', 'gimbal', 'videoDelayMs', 'presentation', 'thirdPerson', 'underwaterAudio',
  'diveMusic', 'procedure', 'beautify', 'vision'];
function careerParams(url, choice) {
  if (choice.contract) url.searchParams.set('contract', choice.contract);
  else url.searchParams.delete('contract');
  if (!choice.contract || !choice.exam) {
    url.searchParams.delete('exam');
    return;
  }
  url.searchParams.set('exam', '1');
  url.searchParams.set('fidelity', 'real');
  for (const name of EXAM_CLEARED_PARAMS) url.searchParams.delete(name);
}

// The game URL for a choice. Parameters the menu does not own (fidelity, cam, gimbal, …) pass through.
export function launchUrl(href, choice, pageProtocol = 'http:') {
  const url = new URL(href);
  // Menu-only staging must not leak into the dive URL (dusk sky, boat stage).
  for (const name of ['replay', 'menu', 'tab', 'menuStage']) url.searchParams.delete(name);
  url.searchParams.set('play', '1');
  url.searchParams.set('model', choice.model);
  url.searchParams.set('ws', normaliseServer(choice.server, pageProtocol));
  url.searchParams.set('room', validRoom(choice.room));
  url.searchParams.set('name', choice.name.trim() || STRINGS.defaultName);
  url.searchParams.set('scenario', choice.scenario);
  url.searchParams.delete('scene');
  url.searchParams.set('seed', '42');
  url.searchParams.set('control', choice.control);
  url.searchParams.set('pad', choice.pad);
  url.searchParams.set('sticker', choice.sticker);
  url.searchParams.set('quality', choice.quality);
  url.searchParams.set('mission', choice.mission);
  if (choice.mission === 'campaign' && choice.chapter) url.searchParams.set('chapter', choice.chapter);
  else url.searchParams.delete('chapter');
  if (choice.intro) url.searchParams.delete('nointro');
  else url.searchParams.set('nointro', '1');
  careerParams(url, choice);
  return url;
}

// Store a launched choice where the game, the desktop shell and the next 快速開始 will read it.
export function rememberChoice(choice) {
  const settings = {};
  for (const key of Object.keys(INTERFACE_DEFAULTS)) settings[key] = !!choice[key];
  settings.intro = !!(choice.introPreference ?? choice.intro);
  write('rov.menuSettings', JSON.stringify(settings));
  if (choice.intro) write(INTRO_SEEN_KEY, '1');
  write('rov.playerName', choice.name.trim() || STRINGS.defaultName);
  write('rov.quality', choice.quality);
  write('rov.operatorVisible', String(settings.pip));
  write('rov.vehicle', choice.model);
  write('rov.sticker', choice.sticker);
  write('rov.mission', choice.mission);
  rememberControlLayout(choice.control);
  const last = {
    model: choice.model,
    mission: choice.mission,
    scenario: choice.scenario,
    chapter: choice.chapter,
    sticker: choice.sticker,
    room: choice.room,
  };
  write(LAST_KEY, JSON.stringify(last));
  globalThis.window?.rovDesktop?.rememberModel?.(choice.model);
  globalThis.window?.rovDesktop?.rememberQuality?.(choice.quality);
}

export function rememberQuality(quality) {
  write('rov.quality', quality);
  globalThis.window?.rovDesktop?.rememberQuality?.(quality);
}

export function rememberInterface(choice) {
  const settings = {};
  for (const key of Object.keys(INTERFACE_DEFAULTS)) settings[key] = !!choice[key];
  settings.intro = !!(choice.introPreference ?? choice.intro);
  write('rov.menuSettings', JSON.stringify(settings));
}
