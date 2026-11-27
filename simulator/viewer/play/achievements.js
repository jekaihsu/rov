// Steam achievements from game events: maps the state stream and finished runs (the results screen's
// `rov-run-result` event) onto the event names of desktop/steam/achievements.json and reports each one once
// through window.rovDesktop.steamEvent(). Internal training builds (edition !== 'steam') never report or show
// achievements. Mapping functions are pure so node --test can check them.
import { achievementsStore } from '../saves/registry.js';

export const ACHIEVEMENT_KEY = 'rov.achievements.v1';
export const LOW_VISIBILITY_M = 1.5;
export const CABLE_DISCIPLINE_MIN = 90;
export const CHAPTER1_CONTRACTS = Object.freeze([
  'c1_pier_level1',
  'c1_pier_level2',
  'c1_hull_fouling',
  'c1_dropped_object',
  'c1_quay_cp',
  'c1_hull_ut',
  'c1_signoff_exam',
]);
export const GUIDE_EVENTS = {
  fish_school: 'evidence_photo',
  coral: 'evidence_photo',
  seagrass: 'evidence_photo',
  kelp: 'evidence_photo',
  seastar: 'evidence_photo',
  engineering: 'evidence_photo',
};
const CONTRACT_EVENTS = {
  c1_pier_level1: 'harbor_clean',
  c1_pier_level2: 'pier_measure',
  c1_hull_fouling: 'hull_loto',
  c1_dropped_object: 'sonar_find',
  c1_quay_cp: 'cp_survey',
  c1_hull_ut: 'ut_survey',
  c1_signoff_exam: 'grade2_exam',
  p1_pool_checkout: 'pool_gold',
  p2_open_water: 'open_water_clean',
};
const DIVE_DEPTH_M = 1;

function untangledCount(state) {
  return (state?.score?.objectives || []).filter(function untangled(objective) {
    return objective.kind === 'untangle' && objective.done;
  }).length;
}

function tetherResult(state) {
  return state?.tether_ops?.result || null;
}

// Events implied by one state frame compared with the previous one (null on the first frame).
export function stateEvents(previous, state) {
  const events = [];
  if (!state) return events;
  const depth = state.pos?.[2] ?? 0;
  if (!state.locked && depth >= DIVE_DEPTH_M) events.push('first_dive');
  if (previous && untangledCount(state) > untangledCount(previous)) events.push('untangled');
  const previousResult = tetherResult(previous);
  const result = tetherResult(state);
  // Only a correct retrace (back to the snag, then free) counts — a wrong exit still sets result.
  if (result && result !== previousResult && result.correct) {
    events.push('untangled');
    events.push('tether_retrace');
  }
  if (state.mission?.mode === 'inspection_coop' && state.mission.status === 'completed') {
    events.push('inspection_coop');
  }
  const observation = state.expedition?.last_observation;
  const previousId = previous?.expedition?.last_observation?.photo_id;
  const entry = observation?.accepted ? observation.entry : null;
  const own = entry && String(entry.photographer) === String(state.vehicle_id);
  if (previous && own && observation.photo_id !== previousId && GUIDE_EVENTS[entry.category]) {
    events.push(GUIDE_EVENTS[entry.category]);
  }
  return events;
}

// The guide category a frame newly recorded for this pilot, if any.
export function observedCategory(previous, state) {
  const observation = state?.expedition?.last_observation;
  if (!previous || !observation?.accepted || !observation.entry) return null;
  if (observation.photo_id === previous.expedition?.last_observation?.photo_id) return null;
  if (String(observation.entry.photographer) !== String(state.vehicle_id)) return null;
  return observation.entry.category;
}

export function chapterAllGold(contracts, ids = CHAPTER1_CONTRACTS) {
  return ids.every(function gold(id) {
    return contracts?.[id]?.medal === 'gold';
  });
}

function measureDone(outcome) {
  if (outcome.measured) return true;
  const items = outcome.career?.line?.deliverables || outcome.deliverables || [];
  return items.some(function item(entry) {
    return entry.kind === 'measure' && entry.done;
  });
}

function careerCompleted(outcome) {
  return outcome?.career?.pay?.outcome === 'complete';
}

// Events earned by a finished run (play/results_model.js / career dive outcome).
export function outcomeEvents(outcome) {
  const events = [];
  if (!outcome?.success) return events;
  if (outcome.kind === 'coop') events.push('inspection_coop');
  if (outcome.kind === 'contract') {
    if (outcome.id === 'recover') events.push('recovery_work');
    if (outcome.id === 'deploy') events.push('deployment_work');
    if (outcome.id === 'inspect') events.push('inspection_coop');
  }
  if (outcome.kind === 'chapter' && outcome.id === 'prologue') events.push('first_dive');
  // Career partials still set success=true; only a full payout counts as a clean finished run.
  if ((outcome.contacts ?? 0) === 0 && (outcome.kind !== 'career' || careerCompleted(outcome))) {
    events.push('zero_collision');
  }

  if (outcome.kind === 'career') {
    const completed = careerCompleted(outcome);
    const medal = outcome.medal;
    const id = outcome.id;
    if (completed) {
      if (id === 'c1_pier_level1' && (outcome.contacts ?? 0) === 0) events.push('harbor_clean');
      if (id === 'p1_pool_checkout' && medal === 'gold') events.push('pool_gold');
      if (id === 'p2_open_water') {
        events.push('prologue_done');
        if ((outcome.contacts ?? 0) === 0) events.push('open_water_clean');
      }
      const mapped = CONTRACT_EVENTS[id];
      if (mapped && mapped !== 'harbor_clean' && mapped !== 'pool_gold' && mapped !== 'open_water_clean') {
        if (mapped === 'grade2_exam') {
          if (outcome.examPassed) events.push('grade2_exam');
        } else {
          events.push(mapped);
        }
      }
      if (outcome.examPassed && outcome.examValid) events.push('real_exam');
      if (chapterAllGold(outcome.contracts)) events.push('chapter1_gold');
    }
    // Measurement / cable discipline can be earned on the dive even when the payout is only partial.
    if (measureDone(outcome) && Number(outcome.visibility_m) <= LOW_VISIBILITY_M) {
      events.push('murk_measure');
    }
    if (!outcome.tetherBroken && Number(outcome.tetherDiscipline) >= CABLE_DISCIPLINE_MIN) {
      events.push('cable_discipline');
    }
  }
  return [...new Set(events)];
}

function readSave(storage) {
  const { value } = achievementsStore.load(storage);
  return {
    earned: Array.isArray(value.earned) ? value.earned : [],
    categories: Array.isArray(value.categories) ? value.categories : [],
  };
}

// report(event) sends to Steam; storage keeps what this device already reported so each event crosses IPC once.
export function createAchievements({ report, storage = globalThis.localStorage, enabled = true }) {
  const save = readSave(storage);
  const earned = new Set(save.earned);
  const categories = new Set(save.categories);
  let previous = null;
  function persist() {
    achievementsStore.save({ earned: [...earned], categories: [...categories] }, storage);
  }
  function unlock(events) {
    if (!enabled) return [];
    const fresh = events.filter(function unseen(event) {
      return !earned.has(event);
    });
    for (const event of fresh) {
      earned.add(event);
      report(event);
    }
    if (fresh.length) persist();
    return fresh;
  }
  function observe(state) {
    if (!enabled) {
      previous = state;
      return [];
    }
    const events = stateEvents(previous, state);
    const category = observedCategory(previous, state);
    if (category && !categories.has(category)) {
      categories.add(category);
      persist();
    }
    previous = state;
    return unlock(events);
  }
  function finished(outcome) {
    return unlock(outcomeEvents(outcome));
  }
  return {
    observe,
    finished,
    get earned() {
      return [...earned];
    },
    get enabled() {
      return enabled;
    },
  };
}

function achievementsEnabled(desktop) {
  return desktop?.edition === 'steam' && typeof desktop?.steamEvent === 'function';
}

// Wires the tracker to the desktop bridge and the results screen; returns {update(state)} for app.js.
// A replay (readOnly) never earns anything. Internal training builds never show or report achievements.
export function installAchievements({ readOnly = false } = {}) {
  const desktop = globalThis.window?.rovDesktop;
  const enabled = !readOnly && achievementsEnabled(desktop);
  function report(event) {
    if (!enabled) return;
    desktop.steamEvent(event, 1).catch(function steamUnavailable(error) {
      console.warn('Steam achievement not reported:', event, error?.message || error);
    });
  }
  const tracker = createAchievements({ report, enabled });
  document.addEventListener('rov-run-result', function runFinished(event) {
    if (!readOnly) tracker.finished(event.detail);
  });
  return {
    update(state) {
      if (!readOnly) tracker.observe(state);
    },
    get earned() {
      return tracker.earned;
    },
    get enabled() {
      return tracker.enabled;
    },
  };
}
