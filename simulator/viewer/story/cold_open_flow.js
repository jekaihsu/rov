// When the cold open plays, and the game URL that plays it (docs/design/cold-open/README.md §4). Pure apart from
// localStorage, so the launch menu (menu/main.js) and node tests share one rule:
//   * a new game (the title's 開始 on a profile that never dived and has no career or story progress) and the first
//     start of the prologue (story list or the career's prologue work order) play the cold open first, once;
//   * the 介面 settings turn it off; 重玩開場 in the story list plays it again (then it may be skipped).
// The cold open is its own campaign entry (campaign/cold_open.json, category `prelude`); the URL that would have
// launched the prologue rides along in `next`, so the prologue itself is untouched.

export const STORAGE_KEY = 'rov.coldOpen.v1';
export const CHAPTER = 'cold_open';
export const SCENARIO = 'cold_open_jacket';
export const PROLOGUE = 'prologue';
// Career work order that wraps the prologue chapter (career/contracts.json); a new game continues into it.
export const PROLOGUE_CONTRACT = 'p0_induction';
// Query flags on the game URL: coldOpen=1 (first play) or coldOpen=replay, and next=<query of the follow-up>.
export const FLAG = 'coldOpen';
export const NEXT = 'next';

function storage() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

export function loadColdOpen() {
  try {
    const value = JSON.parse(storage()?.getItem(STORAGE_KEY) || '{}');
    return {seen: !!value?.seen, enabled: value?.enabled !== false};
  } catch {
    return {seen: false, enabled: true};
  }
}

function save(record) {
  try {
    storage()?.setItem(STORAGE_KEY, JSON.stringify(record));
  } catch {
    // Private windows may refuse storage; the cold open then simply plays again next time.
  }
}

export function markColdOpenSeen() {
  save({...loadColdOpen(), seen: true});
}

export function setColdOpenEnabled(enabled) {
  save({...loadColdOpen(), enabled: !!enabled});
}

// Whether this choice starts the prologue (story chapter, or the career work order that runs it).
export function startsPrologue(choice) {
  return choice?.mission === 'campaign' && choice.chapter === PROLOGUE && !choice.multiplayer && !choice.joining;
}

// Whether launching this choice plays the cold open first.
export function playsBefore(choice, record = loadColdOpen()) {
  return record.enabled && !record.seen && startsPrologue(choice);
}

// A new game: never launched a dive (no last session), no career money, hours or finished work, no story chapter.
export function isNewGame(profile = {}, record = loadColdOpen()) {
  const {hasLastSession = false, career = null, completedChapters = []} = profile;
  if (!record.enabled || record.seen || hasLastSession) return false;
  if (completedChapters.length) return false;
  if (!career) return true;
  const logbook = Array.isArray(career.logbook) ? career.logbook : [];
  return !logbook.length && !(Number(career.money) > 0);
}

/**
 * The game URL that plays the cold open, from the URL that would have launched the follow-up (the prologue).
 * Both a new game and a replay return to the main menu with the current language and connection settings.
 */
export function coldOpenUrl(followUp, {replay = false} = {}) {
  const url = new URL(followUp);
  const next = new URL(followUp);
  url.searchParams.set('mission', 'campaign');
  url.searchParams.set('chapter', CHAPTER);
  url.searchParams.set('scenario', SCENARIO);
  url.searchParams.set('nointro', '1');
  url.searchParams.set(FLAG, replay ? 'replay' : '1');
  // A room of its own: the follow-up then joins its usual room fresh, with the campaign idle.
  url.searchParams.set('room', coldOpenRoom(url.searchParams.get('room')));
  for (const name of ['contract', 'exam', 'procedure']) url.searchParams.delete(name);
  for (const name of ['play', 'chapter', 'contract', 'mission', 'scenario', 'exam', 'procedure', 'nointro']) {
    next.searchParams.delete(name);
  }
  next.searchParams.set('menu', 'main');
  url.searchParams.set(NEXT, next.search);
  return url;
}

// The cold open's room: the launch's room name with a suffix, within the 32-character room limit.
export function coldOpenRoom(room) {
  return `${String(room || 'training').slice(0, 26)}-cold`;
}

// Where the game goes when the cold open ends: the follow-up launch (same page, new query), or the menu.
export function followUpUrl(href) {
  const url = new URL(href);
  const next = url.searchParams.get(NEXT);
  const target = new URL(url.pathname, url.origin);
  if (next && next.startsWith('?')) target.search = next;
  else target.search = '?menu=main';
  return target.href;
}
