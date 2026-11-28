// Local-only student practice records. Stored in localStorage; export files are
// downloads. Nothing is uploaded to a server.

import {buildScorecard} from './scorecard.js';

export const STORAGE_KEY = 'rov.training.records.v1';
export const MAX_RECORDS = 200;

function storage(host = globalThis) {
  try {
    return host.localStorage || null;
  } catch {
    return null;
  }
}

export function listRecords(host = globalThis) {
  try {
    const raw = storage(host)?.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveRecord(scorecard, host = globalThis) {
  const records = listRecords(host);
  records.push(scorecard);
  const trimmed = records.slice(-MAX_RECORDS);
  try {
    storage(host)?.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    // Private mode may refuse storage; the caller still holds the scorecard for export.
  }
  return trimmed;
}

export function clearRecords(host = globalThis) {
  try {
    storage(host)?.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function finalizeSession({metrics, lesson, student, endedAt, host} = {}) {
  const scorecard = buildScorecard({metrics, lesson, student, endedAt});
  saveRecord(scorecard, host);
  return scorecard;
}

export function linkTrainingReplay(card, replayId, host = globalThis) {
  const records = listRecords(host);
  const match = records.findLast(row => row.startedAt === card.startedAt && row.lessonId === card.lessonId);
  if (!match) return;
  match.replayId = replayId;
  storage(host)?.setItem(STORAGE_KEY, JSON.stringify(records));
}
