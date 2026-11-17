// Career save model of ROV Solution: one versioned localStorage record (rov.career.v1) holding money, the dive
// logbook (real and assisted hours kept apart), the YX licence grade, reputation per client type, owned equipment
// and cosmetics, vehicle Block levels and per-contract progress. Pure functions over an injected storage so
// node --test can load it; the desktop shell also receives a copy through the collection store (Steam Cloud
// later). A new save migrates the older story progress (rov.campaign.v1) and best scores (rov.results.v1)
// without changing those records, so nothing the earlier versions saved is lost.

import { localize } from '../i18n/index.js';
export const CAREER_KEY = 'rov.career.v1';
export const CAREER_VERSION = 1;
export const CAMPAIGN_KEY = 'rov.campaign.v1';
export const RESULTS_KEY = 'rov.results.v1';
export const EXPORT_FORMAT = 'rov-career';
export const LOGBOOK_LIMIT = 400;
export const FLEET = ['x1', 'bluerov2_heavy', 'falcon'];
export const OUTCOMES = ['complete', 'partial', 'aborted'];
export const MEDAL_IDS = ['gold', 'silver', 'bronze', 'none'];
// One-off "previous experience" bonus per medal already earned in the older versions, capped.
export const LEGACY_BONUS = { gold: 600, silver: 400, bronze: 200 };
export const LEGACY_BONUS_CAP = 6000;
// Story chapters of the older versions that are also career contracts.
export const LEGACY_CHAPTER_CONTRACTS = { prologue: 'p0_induction' };
const DESKTOP_KIND = 'career-save';

const STRINGS = localize('career.save', {
  badImport: '這不是 ROV Solution 的職涯存檔。',
  newerImport: '這份存檔來自較新的版本，請先更新遊戲再匯入。',
  legacyTitle: '舊版劇情紀錄：{chapter}',
});

function isObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function finite(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function amount(value) {
  return Math.max(0, Math.round(finite(value)));
}

function text(value, limit = 200) {
  return typeof value === 'string' ? value.slice(0, limit) : '';
}

function strings(value, limit = 200) {
  if (!Array.isArray(value)) return [];
  const list = value.filter(function isText(entry) {
    return typeof entry === 'string' && entry.length > 0 && entry.length <= 64;
  });
  return [...new Set(list)].slice(0, limit);
}

function iso(now) {
  return new Date(now).toISOString();
}

function defaultVehicles() {
  const vehicles = {};
  for (const id of FLEET) vehicles[id] = { block: 1 };
  return vehicles;
}

/** A fresh career: no licence, no money, Block 1 everywhere. */
export function defaultSave(now = Date.now()) {
  return {
    version: CAREER_VERSION,
    createdAt: iso(now),
    updatedAt: iso(now),
    money: 0,
    licence: 'none',
    endorsements: [],
    reputation: {},
    owned: [],
    vehicles: defaultVehicles(),
    contracts: {},
    logbook: [],
    hours: { real_s: 0, assisted_s: 0 },
    activeDive: null,
    fidelityStash: null,
    migration: null,
  };
}

function normalizeDeliverable(entry) {
  return {
    id: text(entry?.id, 64),
    label: text(entry?.label, 120),
    done: !!entry?.done,
    reading: text(entry?.reading, 120),
  };
}

/** One logbook line as stored; unknown fields are dropped and numbers clamped. */
export function normalizeLogEntry(entry) {
  const outcome = OUTCOMES.includes(entry?.outcome) ? entry.outcome : 'aborted';
  const medal = MEDAL_IDS.includes(entry?.medal) ? entry.medal : 'none';
  const deliverables = Array.isArray(entry?.deliverables) ? entry.deliverables.slice(0, 40) : [];
  return {
    id: text(entry?.id, 96),
    date: text(entry?.date, 40),
    contract: text(entry?.contract, 64),
    title: text(entry?.title, 120),
    site: text(entry?.site, 64),
    vehicle: text(entry?.vehicle, 32),
    block: Math.max(1, Math.round(finite(entry?.block, 1))),
    duration_s: Math.max(0, finite(entry?.duration_s)),
    real_s: Math.max(0, finite(entry?.real_s)),
    assisted_s: Math.max(0, finite(entry?.assisted_s)),
    outcome,
    medal,
    score: Math.max(0, Math.min(100, Math.round(finite(entry?.score)))),
    pay: amount(entry?.pay),
    deliverables: deliverables.map(normalizeDeliverable),
    exam: !!entry?.exam,
    examPassed: !!entry?.examPassed,
    legacy: !!entry?.legacy,
  };
}

function normalizeContracts(value) {
  const contracts = {};
  if (!isObject(value)) return contracts;
  for (const [id, entry] of Object.entries(value)) {
    if (!/^[a-z0-9_]{1,64}$/.test(id) || !isObject(entry)) continue;
    contracts[id] = {
      completed: amount(entry.completed),
      attempts: amount(entry.attempts),
      best: Math.max(0, Math.min(100, Math.round(finite(entry.best)))),
      medal: MEDAL_IDS.includes(entry.medal) ? entry.medal : 'none',
    };
  }
  return contracts;
}

function normalizeReputation(value) {
  const reputation = {};
  if (!isObject(value)) return reputation;
  for (const [client, points] of Object.entries(value)) {
    if (/^[a-z_]{1,32}$/.test(client)) reputation[client] = amount(points);
  }
  return reputation;
}

function normalizeVehicles(value) {
  const vehicles = defaultVehicles();
  if (!isObject(value)) return vehicles;
  for (const id of FLEET) vehicles[id] = { block: Math.max(1, Math.round(finite(value[id]?.block, 1))) };
  return vehicles;
}

function normalizeActive(value) {
  if (!isObject(value) || !text(value.contract, 64)) return null;
  return {
    id: text(value.id, 96),
    contract: text(value.contract, 64),
    title: text(value.title, 120),
    site: text(value.site, 64),
    startedAt: text(value.startedAt, 40),
    vehicle: text(value.vehicle, 32),
    block: Math.max(1, Math.round(finite(value.block, 1))),
    exam: !!value.exam,
    real_s: Math.max(0, finite(value.real_s)),
    assisted_s: Math.max(0, finite(value.assisted_s)),
    duration_s: Math.max(0, finite(value.duration_s)),
    deliverables: Array.isArray(value.deliverables) ? value.deliverables.slice(0, 40).map(normalizeDeliverable) : [],
  };
}

/** Coerces any parsed object into a valid save of this version. */
export function normalizeSave(raw, now = Date.now()) {
  const base = defaultSave(now);
  if (!isObject(raw)) return base;
  const logbook = Array.isArray(raw.logbook) ? raw.logbook.slice(-LOGBOOK_LIMIT).map(normalizeLogEntry) : [];
  return {
    version: CAREER_VERSION,
    createdAt: text(raw.createdAt, 40) || base.createdAt,
    updatedAt: text(raw.updatedAt, 40) || base.updatedAt,
    money: amount(raw.money),
    licence: /^[a-z0-9_]{1,32}$/.test(raw.licence || '') ? raw.licence : 'none',
    endorsements: strings(raw.endorsements, 32),
    reputation: normalizeReputation(raw.reputation),
    owned: strings(raw.owned, 100),
    vehicles: normalizeVehicles(raw.vehicles),
    contracts: normalizeContracts(raw.contracts),
    logbook,
    hours: {
      real_s: Math.max(0, finite(raw.hours?.real_s)),
      assisted_s: Math.max(0, finite(raw.hours?.assisted_s)),
    },
    activeDive: normalizeActive(raw.activeDive),
    fidelityStash: typeof raw.fidelityStash === 'string' ? raw.fidelityStash.slice(0, 20000) : null,
    migration: isObject(raw.migration) ? {
      at: text(raw.migration.at, 40),
      chapters: strings(raw.migration.chapters, 40),
      records: amount(raw.migration.records),
      bonus: amount(raw.migration.bonus),
    } : null,
  };
}

function readJson(storage, key) {
  try {
    const value = JSON.parse(storage?.getItem(key) || 'null');
    return isObject(value) ? value : null;
  } catch {
    return null;
  }
}

/**
 * Brings the progress of the older story campaign and the best-score table into a new career: chapters that are
 * also contracts count as done, earlier chapter runs enter the logbook (their fidelity is unknown, so as assisted
 * hours), and every medal pays a small one-off bonus. The older records themselves are left untouched.
 */
export function migrateLegacy(save, storage, now = Date.now()) {
  const campaign = readJson(storage, CAMPAIGN_KEY);
  const records = readJson(storage, RESULTS_KEY);
  if (!campaign && !records) return save;
  const chapters = strings(campaign?.completed, 40);
  for (const chapter of chapters) {
    const contract = LEGACY_CHAPTER_CONTRACTS[chapter];
    if (contract) save.contracts[contract] = { completed: 1, attempts: 1, best: 0, medal: 'none' };
  }
  const runs = Array.isArray(campaign?.results) ? campaign.results.slice(-40) : [];
  runs.forEach(function logRun(run, index) {
    const elapsed = Math.max(0, finite(run?.elapsed));
    const chapter = text(run?.chapter, 64);
    save.logbook.push(normalizeLogEntry({
      id: `legacy-${index}`,
      date: iso(now),
      contract: LEGACY_CHAPTER_CONTRACTS[chapter] || '',
      title: STRINGS.legacyTitle.replace('{chapter}', chapter),
      outcome: 'complete',
      duration_s: elapsed,
      assisted_s: elapsed,
      legacy: true,
    }));
    save.hours.assisted_s += elapsed;
  });
  let bonus = 0;
  let count = 0;
  for (const record of Object.values(records || {})) {
    if (!isObject(record)) continue;
    count += 1;
    bonus += LEGACY_BONUS[record.medal] || 0;
  }
  bonus = Math.min(LEGACY_BONUS_CAP, bonus);
  save.money += bonus;
  save.migration = { at: iso(now), chapters, records: count, bonus };
  return save;
}

function desktopAvailable() {
  return typeof globalThis.window?.rovDesktop?.collection === 'function';
}

/** Desktop only: keeps a copy in the shell's collection store so it can be synced (Steam Cloud) later. */
export async function mirrorToDesktop(save) {
  if (!desktopAvailable()) return false;
  try {
    const store = await import('../collection_store.js');
    await store.saveResult({ kind: DESKTOP_KIND, save: JSON.parse(JSON.stringify(save)) });
    return true;
  } catch {
    return false;
  }
}

/** Desktop only: the newest copy the shell keeps, or null. */
export async function readDesktopCopy() {
  if (!desktopAvailable()) return null;
  try {
    const store = await import('../collection_store.js');
    const index = await store.listCollection();
    const copy = (index.results || []).filter(function isCareer(entry) {
      return entry.kind === DESKTOP_KIND;
    }).at(-1);
    return copy ? normalizeSave(copy.save) : null;
  } catch {
    return null;
  }
}

function defaultStorage() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

/** The stored career, or a fresh one (migrated from the older records and stored right away). */
export function loadCareer({ storage = defaultStorage(), now = Date.now() } = {}) {
  const raw = readJson(storage, CAREER_KEY);
  if (raw) return normalizeSave(raw, now);
  const save = migrateLegacy(defaultSave(now), storage, now);
  storeCareer(save, { storage, now, mirror: false });
  return save;
}

/** Writes the save; mirror sends the desktop copy too (settled dives and purchases, not every progress tick). */
export function storeCareer(save, { storage = defaultStorage(), now = Date.now(), mirror = true } = {}) {
  save.updatedAt = iso(now);
  try {
    storage?.setItem(CAREER_KEY, JSON.stringify(save));
  } catch {
    // Private windows may refuse storage; the session keeps its career in memory.
  }
  if (mirror) mirrorToDesktop(save);
  return save;
}

/** Text of an export file. */
export function exportCareer(save, now = Date.now()) {
  return JSON.stringify({ format: EXPORT_FORMAT, version: CAREER_VERSION, exportedAt: iso(now), save }, null, 2);
}

/** The save inside an export file; throws an Error with a player-facing message when it cannot be used. */
export function importCareer(source, now = Date.now()) {
  let archive;
  try {
    archive = typeof source === 'string' ? JSON.parse(source) : source;
  } catch {
    throw new Error(STRINGS.badImport);
  }
  if (!isObject(archive) || archive.format !== EXPORT_FORMAT || !isObject(archive.save)) {
    throw new Error(STRINGS.badImport);
  }
  if (finite(archive.version) > CAREER_VERSION) throw new Error(STRINGS.newerImport);
  return normalizeSave(archive.save, now);
}

/** Adds one dive to the logbook and the hour totals. */
export function logDive(save, entry) {
  const line = normalizeLogEntry(entry);
  save.logbook.push(line);
  if (save.logbook.length > LOGBOOK_LIMIT) save.logbook.splice(0, save.logbook.length - LOGBOOK_LIMIT);
  save.hours.real_s += line.real_s;
  save.hours.assisted_s += line.assisted_s;
  return line;
}

/** Real-mode pilot hours (the only hours that count toward a licence). */
export function realHours(save) {
  return (save?.hours?.real_s || 0) / 3600;
}

export function assistedHours(save) {
  return (save?.hours?.assisted_s || 0) / 3600;
}
