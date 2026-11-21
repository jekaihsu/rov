// Steam achievements from game events: maps the state stream and finished runs (the results screen's
// `rov-run-result` event) onto the event names of desktop/steam/achievements.json and reports each one once
// through window.rovDesktop.steamEvent(). In a browser there is no desktop bridge and this is a no-op apart from
// remembering what was earned on this device. The mapping functions are pure so node --test can check them.
import { achievementsStore } from '../saves/registry.js';

export const ACHIEVEMENT_KEY = 'rov.achievements.v1';
// Collection categories (qysim/expedition.py BIOLOGY, plus engineering photos) → guide achievements.
export const GUIDE_EVENTS = {
  fish_school: 'guide_fish',
  coral: 'guide_coral',
  seagrass: 'guide_seagrass',
  kelp: 'guide_seagrass',
  seastar: 'guide_other',
  engineering: 'guide_structure',
};
export const GUIDE_CATEGORIES = ['coral', 'seastar', 'kelp', 'seagrass', 'fish_school'];
const CONTRACT_EVENTS = { inspect: 'inspection', recover: 'recovery', deploy: 'deployment' };
const DIVE_DEPTH_M = 1;

function untangledCount(state) {
  return (state?.score?.objectives || []).filter(function untangled(objective) {
    return objective.kind === 'untangle' && objective.done;
  }).length;
}

function connectedPilots(state) {
  return (state?.room?.players || []).filter(function connected(player) {
    return player.connected !== false;
  }).length;
}

// Events implied by one state frame compared with the previous one (null on the first frame).
export function stateEvents(previous, state) {
  const events = [];
  if (!state) return events;
  const depth = state.pos?.[2] ?? 0;
  if (!state.locked && depth >= DIVE_DEPTH_M) events.push('first_dive');
  if (previous && (state.photos || 0) > (previous.photos || 0)) events.push('first_photo');
  if (previous && untangledCount(state) > untangledCount(previous)) events.push('untangled');
  if (connectedPilots(state) >= 3) events.push('three_pilots');
  if (state.mission?.mode === 'inspection_coop' && state.mission.status === 'completed') events.push('inspection');
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

// Events earned by a finished run (play/results_model.js outcome).
export function outcomeEvents(outcome) {
  const events = [];
  if (!outcome?.success) return events;
  if (outcome.kind === 'scenario' || outcome.kind === 'drill') events.push('scenario');
  if (outcome.kind === 'coop') events.push('inspection');
  if (outcome.kind === 'contract') {
    const event = CONTRACT_EVENTS[outcome.id];
    if (event) events.push(event);
  }
  if (outcome.kind === 'chapter' && outcome.id === 'prologue') events.push('first_dive');
  if ((outcome.contacts ?? 0) === 0) events.push('zero_collision');
  return events;
}

export function guideComplete(categories) {
  return GUIDE_CATEGORIES.every(function seen(category) {
    return categories.includes(category);
  });
}

function readSave(storage) {
  const { value } = achievementsStore.load(storage);
  return {
    earned: Array.isArray(value.earned) ? value.earned : [],
    categories: Array.isArray(value.categories) ? value.categories : [],
  };
}

// report(event) sends to Steam; storage keeps what this device already reported so each event crosses IPC once.
export function createAchievements({ report, storage = globalThis.localStorage }) {
  const save = readSave(storage);
  const earned = new Set(save.earned);
  const categories = new Set(save.categories);
  let previous = null;
  function persist() {
    achievementsStore.save({ earned: [...earned], categories: [...categories] }, storage);
  }
  function unlock(events) {
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
    const events = stateEvents(previous, state);
    const category = observedCategory(previous, state);
    if (category && !categories.has(category)) {
      categories.add(category);
      persist();
    }
    if (guideComplete([...categories])) events.push('guide_complete');
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
  };
}

// Wires the tracker to the desktop bridge and the results screen; returns {update(state)} for app.js.
// A replay (readOnly) never earns anything.
export function installAchievements({ readOnly = false } = {}) {
  const desktop = globalThis.window?.rovDesktop;
  function report(event) {
    if (typeof desktop?.steamEvent !== 'function') return;
    desktop.steamEvent(event, 1).catch(function steamUnavailable(error) {
      console.warn('Steam achievement not reported:', event, error?.message || error);
    });
  }
  const tracker = createAchievements({ report });
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
  };
}
