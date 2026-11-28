// Build a local student scorecard from session metrics. Pass/fail stays provisional
// (docs/training/curriculum.md; research report training section). No upload.

import {photoQualitySummary} from './metrics.js';

export const CSV_COLUMNS = [
  'started_at',
  'ended_at',
  'lesson_id',
  'lesson_title',
  'level',
  'elapsed_s',
  'tether_contact_episodes',
  'max_tension_n',
  'collisions',
  'severe_collisions',
  'photos',
  'photo_mean_standoff_m',
  'photo_quality',
  'procedure_in_order',
  'objectives_done',
  'objectives_total',
  'finished',
  'failed',
  'score',
  'fidelity_preset',
  'fidelity_left_real',
  'assisted_used',
  'pass_provisional',
  'pass_status',
];

function csvEscape(value) {
  const text = value == null ? '' : String(value);
  if (/[",\n\r]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

// Scorer publishes "臍帶纜斷裂"; older event copy used "斷纜".
export function isTetherBreakFailure(failed) {
  if (typeof failed !== 'string' || !failed) return false;
  return failed.includes('臍帶纜斷裂') || failed.includes('斷纜')
    || /tether[_\s-]?break/i.test(failed);
}

export function evaluatePass(metrics, lesson = {}) {
  // Mirrors curriculum common candidates; every threshold remains provisional.
  const failed = !!(metrics?.failed);
  const broken = isTetherBreakFailure(metrics?.failed);
  const severe = (metrics?.severeCollisions || 0) >= 3;
  const inOrder = metrics?.procedureInOrder !== false;
  const finishedOrAbort = !!(metrics?.finished) || failed;
  const leftReal = !!metrics?.fidelityLeftReal;
  let pass = finishedOrAbort && !broken && !severe && inOrder;
  // Assisted / non-real fidelity is recorded and blocks an automatic pass mark.
  if (leftReal || metrics?.assistedUsed) pass = false;
  return {
    passProvisional: pass,
    passStatus: lesson.passStatus || lesson.pass_status
      || '暫定，待資深操作員基準航次校準',
    reasons: [
      broken ? 'tether_break' : null,
      severe ? 'severe_collisions' : null,
      !inOrder ? 'procedure_out_of_order' : null,
      leftReal ? 'fidelity_not_real' : null,
      metrics?.assistedUsed ? 'assist_used' : null,
      !finishedOrAbort ? 'incomplete' : null,
    ].filter(Boolean),
  };
}

export function buildScorecard({metrics, lesson = {}, student = '', endedAt = null} = {}) {
  const photo = photoQualitySummary(metrics);
  const verdict = evaluatePass(metrics, lesson);
  const ended = endedAt || new Date().toISOString();
  return {
    version: 1,
    localOnly: true,
    startedAt: metrics?.startedAt || ended,
    endedAt: ended,
    student: student || '',
    lessonId: lesson.id || metrics?.lessonId || '',
    lessonTitle: lesson.title || '',
    level: lesson.level || '',
    goal: lesson.goal || '',
    criteria: lesson.criteria || '',
    elapsedS: metrics?.elapsedS ?? 0,
    tetherContactEpisodes: metrics?.tetherContactEpisodes ?? 0,
    maxTensionN: Number((metrics?.maxTensionN ?? 0).toFixed?.(1) ?? metrics?.maxTensionN ?? 0),
    collisions: metrics?.collisions ?? 0,
    severeCollisions: metrics?.severeCollisions ?? 0,
    photos: photo.photos,
    photoMeanStandoffM: photo.meanStandoffM,
    photoQuality: photo.label,
    procedureInOrder: metrics?.procedureInOrder !== false,
    objectivesDone: metrics?.objectivesDone ?? 0,
    objectivesTotal: metrics?.objectivesTotal ?? 0,
    finished: !!metrics?.finished,
    failed: metrics?.failed || '',
    score: metrics?.score,
    fidelityPreset: metrics?.fidelityPreset || 'real',
    fidelityLeftReal: !!metrics?.fidelityLeftReal,
    assistedUsed: !!metrics?.assistedUsed,
    injections: Array.isArray(metrics?.injections) ? metrics.injections : [],
    passProvisional: verdict.passProvisional,
    passStatus: verdict.passStatus,
    reasons: verdict.reasons,
  };
}

export function scorecardToRow(scorecard) {
  return {
    started_at: scorecard.startedAt,
    ended_at: scorecard.endedAt,
    lesson_id: scorecard.lessonId,
    lesson_title: scorecard.lessonTitle,
    level: scorecard.level,
    elapsed_s: scorecard.elapsedS,
    tether_contact_episodes: scorecard.tetherContactEpisodes,
    max_tension_n: scorecard.maxTensionN,
    collisions: scorecard.collisions,
    severe_collisions: scorecard.severeCollisions,
    photos: scorecard.photos,
    photo_mean_standoff_m: scorecard.photoMeanStandoffM ?? '',
    photo_quality: scorecard.photoQuality,
    procedure_in_order: scorecard.procedureInOrder ? 1 : 0,
    objectives_done: scorecard.objectivesDone,
    objectives_total: scorecard.objectivesTotal,
    finished: scorecard.finished ? 1 : 0,
    failed: scorecard.failed,
    score: scorecard.score ?? '',
    fidelity_preset: scorecard.fidelityPreset,
    fidelity_left_real: scorecard.fidelityLeftReal ? 1 : 0,
    assisted_used: scorecard.assistedUsed ? 1 : 0,
    pass_provisional: scorecard.passProvisional ? 1 : 0,
    pass_status: scorecard.passStatus,
  };
}

export function recordsToCsv(records) {
  const lines = [CSV_COLUMNS.join(',')];
  for (const record of records || []) {
    const row = scorecardToRow(record);
    lines.push(CSV_COLUMNS.map(function cell(key) {
      return csvEscape(row[key]);
    }).join(','));
  }
  return `${lines.join('\n')}\n`;
}
