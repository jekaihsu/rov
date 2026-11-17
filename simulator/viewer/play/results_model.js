// Results data for the end-of-run screen: what the run earned and how it is presented. Pure functions over the
// state the server already sends (score of scenario training and co-op inspection, campaign results, expedition
// contract results), the medal thresholds, and the local best-score record the menu lists read back.
// No DOM here, so node --test can load it. Medals and the chapter/contract scores are a presentation layer only:
// scenario scores stay the server's, and nothing here is a training standard.
import { vehicleName, vehicleRole } from '../fleet_names.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('play.results_model', {
  rows: {
    objectives: '任務目標',
    time: '時間',
    tether: '纜線管理',
    contacts: '碰撞與接觸',
    procedure: '作業程序',
    other: '其他扣分',
  },
  kinds: {
    scenario: '場景訓練',
    coop: '協作巡檢',
    chapter: '劇情',
    drill: '事故演練',
    contract: '工程委託',
    career: 'YX 工單',
  },
  timesOne: '{n} 次',
  times: '{n} 次',
  noContacts: '無碰撞',
  tetherBroken: '纜線斷裂',
  tetherClean: '張力正常',
  overloadOne: '過載 {n} 次',
  overload: '過載 {n} 次',
  contract: '委託完成',
  medals: { gold: '金牌', silver: '銀牌', bronze: '銅牌', none: '無獎章' },
  rewards: {
    first_dive: '首次下潛徽章',
    harbor_badge: '港灣巡檢徽章',
    hull_badge: '船殼巡檢徽章',
    harbor_signoff_badge: '交班複查徽章',
    offshore_badge: '離岸作業徽章',
    reef_badge: '礁區作業徽章',
    wreck_badge: '沉船調查徽章',
    ending_open_question: '結局：留下未解的問題',
    ending_evidence_complete: '結局：證據齊全',
  },
  unlockSticker: '機身貼紙解鎖：{name}',
  unlockVehicle: '作業載具解鎖：{name}',
  stickers: { dive: '潛水旗' },
  vehicles: { falcon: `${vehicleName('falcon')}（${vehicleRole('falcon')}）` },
  unknownReward: '獎勵：{id}',
});

// Medal thresholds as data (score 0–100). A failed run never earns a medal.
export const MEDALS = [
  { id: 'gold', min: 90 },
  { id: 'silver', min: 75 },
  { id: 'bronze', min: 50 },
];
// Presentation scoring for chapters and contracts, which the server reports as facts rather than a score.
export const CHAPTER_SCORING = {
  contactPoints: 5,
  contactCap: 40,
  overloadPoints: 10,
  overloadCap: 30,
  brokenPoints: 50,
};
export const RESULTS_KEY = 'rov.results.v1';

export function medalFor(score, success = true) {
  if (!success || !Number.isFinite(score)) return 'none';
  return MEDALS.find(function reached(medal) {
    return score >= medal.min;
  })?.id || 'none';
}

export function medalLabel(id) {
  return STRINGS.medals[id] || STRINGS.medals.none;
}

export function kindLabel(kind) {
  return STRINGS.kinds[kind] || '';
}

export function formatTime(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  return `${String(minutes).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

// one: the singular template (English "1 time"); the other languages use the same text for both.
function count(text, n, one = text) {
  return (n === 1 ? one : text).replace('{n}', String(n));
}

function sumPoints(penalties, prefix) {
  return penalties.filter(function matches(penalty) {
    return String(penalty.reason || '').startsWith(prefix);
  }).reduce(function add(total, penalty) {
    return total + (Number(penalty.points) || 0);
  }, 0);
}

function countOf(penalties, prefix) {
  return penalties.filter(function matches(penalty) {
    return String(penalty.reason || '').startsWith(prefix);
  }).length;
}

// Score breakdown of a server score (qysim/scenarios.py Scorer.as_dict, mission_modes.score_state, procedure).
export function scoreRows(score = {}, limit = null) {
  const objectives = score.objectives || [];
  const done = objectives.filter(function finished(objective) {
    return objective.done;
  }).length;
  const total = objectives.length;
  const penalties = score.penalties || [];
  const contacts = sumPoints(penalties, '碰撞');
  const tether = sumPoints(penalties, '纜線');
  const procedure = Number(score.procedure_penalty) || 0;
  const other = Math.max(0, (Number(score.penalty_total) || 0) - contacts - tether - procedure);
  const contactCount = countOf(penalties, '碰撞');
  const rows = [
    {
      id: 'objectives',
      label: STRINGS.rows.objectives,
      detail: `${done}/${total}`,
      points: Math.round(100 * done / Math.max(1, total)),
    },
    {
      id: 'time',
      label: STRINGS.rows.time,
      detail: limit ? `${formatTime(score.elapsed)} / ${formatTime(limit)}` : formatTime(score.elapsed),
      points: null,
    },
    {
      id: 'tether',
      label: STRINGS.rows.tether,
      detail: tether ? count(STRINGS.overload, countOf(penalties, '纜線'), STRINGS.overloadOne) : STRINGS.tetherClean,
      points: -tether,
    },
    {
      id: 'contacts',
      label: STRINGS.rows.contacts,
      detail: contactCount ? count(STRINGS.times, contactCount, STRINGS.timesOne) : STRINGS.noContacts,
      points: -contacts,
    },
  ];
  if (procedure) rows.push({ id: 'procedure', label: STRINGS.rows.procedure, detail: '', points: -procedure });
  if (other) rows.push({ id: 'other', label: STRINGS.rows.other, detail: '', points: -other });
  return rows;
}

// Scenario training or co-op inspection that just finished or failed.
export function scoreOutcome(state, world) {
  const score = state.score || {};
  const coop = state.mission?.mode === 'inspection_coop';
  const key = world?.scenario?.key || state.scenario || '';
  const limit = coop ? state.mission?.time_limit : world?.scenario?.time_limit_s;
  const success = !!score.finished && !score.failed;
  const value = Math.max(0, Math.round(Number(score.score) || 0));
  const kind = coop ? 'coop' : 'scenario';
  return {
    kind,
    id: key,
    recordKey: `${kind}:${key}`,
    title: world?.scenario?.name || key,
    success,
    reason: score.failed || '',
    score: value,
    medal: medalFor(value, success),
    elapsed: score.elapsed || 0,
    limit: limit || null,
    rows: scoreRows(score, limit),
    contacts: countOf(score.penalties || [], '碰撞'),
    rewards: [],
    next: null,
  };
}

export function rewardLabel(id) {
  return STRINGS.rewards[id] || STRINGS.unknownReward.replace('{id}', id);
}

// Unlock labels for what a chapter opened (state.campaign.unlocks before and after).
export function unlockLabels(before = {}, after = {}) {
  const labels = [];
  for (const sticker of after.stickers || []) {
    if ((before.stickers || []).includes(sticker)) continue;
    labels.push(STRINGS.unlockSticker.replace('{name}', STRINGS.stickers[sticker] || sticker));
  }
  for (const vehicle of after.vehicles || []) {
    if ((before.vehicles || []).includes(vehicle)) continue;
    labels.push(STRINGS.unlockVehicle.replace('{name}', STRINGS.vehicles[vehicle] || vehicle));
  }
  return labels;
}

// A completed campaign chapter (qysim/campaign Campaign.update result entry) with presentation scoring.
export function chapterOutcome({ campaign, start = {}, overloads = 0 }) {
  const result = (campaign.results || []).at(-1) || {};
  const chapterId = result.chapter || campaign.chapter;
  const chapter = (campaign.chapters || []).find(function byId(entry) {
    return entry.id === chapterId;
  }) || {};
  const scoring = CHAPTER_SCORING;
  const collisions = Number(result.collisions) || 0;
  const contacts = Math.min(scoring.contactCap, collisions * scoring.contactPoints);
  const broken = !!result.tether_broken;
  const tether = broken ? scoring.brokenPoints : Math.min(scoring.overloadCap, overloads * scoring.overloadPoints);
  const value = Math.max(0, 100 - contacts - tether);
  const rewards = (campaign.rewards || []).filter(function earned(id) {
    return !(start.rewards || []).includes(id);
  }).map(rewardLabel);
  rewards.push(...unlockLabels(start.unlocks, campaign.unlocks));
  const drill = chapter.category === 'incident';
  const nextId = drill ? null : campaign.next_story;
  const next = (campaign.chapters || []).find(function byId(entry) {
    return entry.id === nextId;
  }) || null;
  let tetherDetail = STRINGS.tetherClean;
  if (broken) tetherDetail = STRINGS.tetherBroken;
  else if (overloads) tetherDetail = count(STRINGS.overload, overloads, STRINGS.overloadOne);
  return {
    kind: drill ? 'drill' : 'chapter',
    id: chapterId,
    recordKey: `chapter:${chapterId}`,
    title: chapter.title || chapterId,
    success: true,
    reason: '',
    score: value,
    medal: medalFor(value, true),
    elapsed: result.elapsed || 0,
    limit: null,
    rows: [
      { id: 'objectives', label: STRINGS.rows.objectives, detail: '✓', points: 100 },
      { id: 'time', label: STRINGS.rows.time, detail: formatTime(result.elapsed), points: null },
      { id: 'tether', label: STRINGS.rows.tether, detail: tetherDetail, points: -tether },
      {
        id: 'contacts',
        label: STRINGS.rows.contacts,
        detail: collisions ? count(STRINGS.times, collisions, STRINGS.timesOne) : STRINGS.noContacts,
        points: -contacts,
      },
    ],
    contacts: collisions,
    rewards,
    next: next ? { id: next.id, title: next.title } : null,
  };
}

// A finished expedition contract (qysim/expedition.py Expedition._finish).
export function contractOutcome(result) {
  const collisions = Number(result.collision_count) || 0;
  const contacts = Math.min(CHAPTER_SCORING.contactCap, collisions * CHAPTER_SCORING.contactPoints);
  const value = Math.max(0, 100 - contacts);
  return {
    kind: 'contract',
    id: result.kind || 'contract',
    recordKey: `contract:${result.kind || 'contract'}`,
    title: result.label || STRINGS.contract,
    success: true,
    reason: result.grade || '',
    score: value,
    medal: medalFor(value, true),
    elapsed: result.elapsed || 0,
    limit: null,
    rows: [
      { id: 'objectives', label: STRINGS.rows.objectives, detail: '✓', points: 100 },
      { id: 'time', label: STRINGS.rows.time, detail: formatTime(result.elapsed), points: null },
      {
        id: 'contacts',
        label: STRINGS.rows.contacts,
        detail: collisions ? count(STRINGS.times, collisions, STRINGS.timesOne) : STRINGS.noContacts,
        points: -contacts,
      },
    ],
    contacts: collisions,
    rewards: [],
    next: null,
  };
}

function isEnded(score) {
  return !!(score?.finished || score?.failed);
}

function chapterRunning(state) {
  return state.campaign?.status === 'active';
}

function contractIds(state) {
  return (state.expedition?.results || []).map(function id(result) {
    return result.id;
  });
}

// Watches the state stream and returns an outcome on the frame a run ends, never for a run that had already
// ended when the page connected. Chapters take precedence over the score of the scenario they run in.
export function createOutcomeWatcher() {
  let primed = false;
  let scoreEnded = false;
  let campaignStatus = '';
  let seenContracts = new Set();
  let chapterStart = null;
  let overloads = 0;
  let warned = false;
  let scene = '';
  function prime(state) {
    primed = true;
    scoreEnded = isEnded(state.score);
    campaignStatus = state.campaign?.status || '';
    seenContracts = new Set(contractIds(state));
    if (campaignStatus === 'active') {
      chapterStart = { rewards: [...(state.campaign.rewards || [])], unlocks: state.campaign.unlocks || {} };
    }
  }
  function trackTether(state) {
    const warn = !!state.tether?.warn;
    if (warn && !warned) overloads += 1;
    warned = warn;
  }
  function observeCampaign(state) {
    const campaign = state.campaign;
    const status = campaign?.status || '';
    const previous = campaignStatus;
    campaignStatus = status;
    if (status === 'active' && previous !== 'active') {
      chapterStart = { rewards: [...(campaign.rewards || [])], unlocks: campaign.unlocks || {} };
      overloads = 0;
      warned = false;
    }
    if (status === 'active') trackTether(state);
    if (status === 'completed' && previous === 'active') {
      return chapterOutcome({ campaign, start: chapterStart || {}, overloads });
    }
    return null;
  }
  function observe(state, world) {
    if (!state) return null;
    const key = `${world?.scenario?.key}:${world?.scenario?.seed}`;
    if (!primed || key !== scene) {
      // A new scene starts a new scorer; whatever it reports on its first frame is not a finished run.
      scene = key;
      scoreEnded = isEnded(state.score);
      if (!primed) prime(state);
      if (!chapterRunning(state)) return null;
    }
    const chapter = observeCampaign(state);
    const ended = isEnded(state.score);
    const newlyEnded = ended && !scoreEnded;
    scoreEnded = ended;
    const contracts = contractIds(state);
    const fresh = contracts.filter(function unseen(id) {
      return !seenContracts.has(id);
    });
    for (const id of contracts) seenContracts.add(id);
    if (chapter) return chapter;
    if (fresh.length) {
      const result = state.expedition.results.find(function byId(entry) {
        return entry.id === fresh.at(-1);
      });
      return contractOutcome(result);
    }
    const inChapter = campaignStatus === 'active';
    const scored = ['scenario_training', 'inspection_coop'].includes(state.mission?.mode);
    const goals = (state.score?.objectives || []).length > 0;
    if (newlyEnded && scored && goals && !inChapter) return scoreOutcome(state, world);
    return null;
  }
  return { observe };
}

function readAll(storage) {
  try {
    const value = JSON.parse(storage?.getItem(RESULTS_KEY) || '{}');
    return value && typeof value === 'object' ? value : {};
  } catch {
    return {};
  }
}

// The best record for one key: {best, medal, at} or null.
export function recordFor(key, storage = globalThis.localStorage) {
  return readAll(storage)[key] || null;
}

const MEDAL_RANK = { none: 0, bronze: 1, silver: 2, gold: 3 };

// Store a run's score when it beats the saved one; returns {best, previous, isBest}.
export function recordResult(outcome, storage = globalThis.localStorage, now = Date.now()) {
  const all = readAll(storage);
  const previous = all[outcome.recordKey] || null;
  const better = !previous || outcome.score > previous.best;
  if (outcome.success && better) {
    all[outcome.recordKey] = { best: outcome.score, medal: outcome.medal, at: now };
  } else if (previous && outcome.success && MEDAL_RANK[outcome.medal] > MEDAL_RANK[previous.medal]) {
    all[outcome.recordKey] = { ...previous, medal: outcome.medal };
  }
  try {
    storage?.setItem(RESULTS_KEY, JSON.stringify(all));
  } catch {
    // Private windows may refuse storage; the screen still shows this run.
  }
  return {
    best: all[outcome.recordKey]?.best ?? null,
    previous: previous?.best ?? null,
    isBest: outcome.success && better,
  };
}
