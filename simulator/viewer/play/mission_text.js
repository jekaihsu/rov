// What the mission line and the training timer say for each play mode. Free exploration and the expedition
// sea have no time limit, objectives or score, so they never show "目標 0/0" or the scene's training time
// limit; scenario training and co-op inspection keep their objective count, penalties and limit. Pure
// functions over the server state and world message, used by app.js and the launch briefing.

import { localize } from '../i18n/index.js';

const STRINGS = localize('play.mission_text', {
  failed: '失敗：{reason}',
  finished: '任務完成',
  progress: '目標 {done}/{total} · 扣分 {penalty}',
  free: '自由探索 · 不計時、不扣分',
  expedition: '海洋探索 · 自由航行，可接工程委託',
  contract: '委託：{label}',
  waiting: '尚未開始',
  next: '下一步：{label}',
  offers: '可在任務卡或下方接取工程委託。',
  chapter: '{title}',
});
const UNTIMED = new Set(['free_explore', 'expedition']);

export function untimedMode(mode) {
  return UNTIMED.has(mode);
}

// Seconds the launch briefing shows: none for untimed modes, 12 min for co-op inspection (qysim/mission_modes.py).
const COOP_LIMIT_S = 720;

export function briefingTimeLimit(mission, facts) {
  if (untimedMode(mission)) return null;
  if (mission === 'inspection_coop') return COOP_LIMIT_S;
  return facts?.timeLimit || null;
}

// The time limit the timer counts against, in seconds, or null when the mode has none.
export function missionTimeLimit(state, world) {
  const mode = state?.mission?.mode;
  if (untimedMode(mode)) return null;
  if (mode === 'inspection_coop') return state.mission.time_limit || null;
  return world?.scenario?.time_limit_s || null;
}

// The score readout: a number only where the mode is scored.
export function scoreValue(state) {
  if (untimedMode(state?.mission?.mode)) return '—';
  return state?.score?.score ?? '—';
}

// One line for the HUD mission readout and the drawer's score state.
export function scoreSummary(state) {
  const mode = state?.mission?.mode;
  const campaign = state?.campaign;
  if (campaign?.status === 'active' && campaign.objective) return campaign.objective;
  if (mode === 'expedition') {
    const label = state.expedition?.active?.label;
    return label ? STRINGS.contract.replace('{label}', label) : STRINGS.expedition;
  }
  if (mode === 'free_explore') return STRINGS.free;
  const score = state?.score;
  if (!score) return STRINGS.waiting;
  if (score.failed) return STRINGS.failed.replace('{reason}', score.failed);
  if (score.finished) return STRINGS.finished;
  const objectives = score.objectives || [];
  const done = objectives.filter(function finished(objective) {
    return objective.done;
  }).length;
  return STRINGS.progress.replace('{done}', String(done)).replace('{total}', String(objectives.length))
    .replace('{penalty}', String(score.penalty_total || 0));
}

// Current objective for the pause menu: a heading line and up to three detail lines.
export function objectiveSummary(state) {
  const lines = [];
  const campaign = state?.campaign;
  if (campaign?.status === 'active') {
    const chapter = (campaign.chapters || []).find(function byId(entry) {
      return entry.id === campaign.chapter;
    });
    if (chapter) lines.push(STRINGS.chapter.replace('{title}', chapter.title));
    const hint = campaign.objective || campaign.node?.hint;
    if (hint) lines.push(hint);
    return lines;
  }
  const mode = state?.mission?.mode;
  if (mode === 'expedition') {
    const active = state.expedition?.active;
    lines.push(scoreSummary(state));
    const step = active?.steps?.find(function open(entry) {
      return !entry.completed;
    });
    if (step) lines.push(STRINGS.next.replace('{label}', step.label));
    if (!active) lines.push(STRINGS.offers);
    return lines;
  }
  if (mode === 'free_explore') return [scoreSummary(state)];
  const objectives = state?.score?.objectives || [];
  const current = objectives.find(function open(objective) {
    return !objective.done;
  });
  if (current?.label) lines.push(STRINGS.next.replace('{label}', current.label));
  lines.push(scoreSummary(state));
  return lines;
}
