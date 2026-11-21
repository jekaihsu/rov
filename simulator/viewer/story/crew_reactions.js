// Advance flight radio on telemetry edges. Callers may supply a presentation clock in seconds.
// Pending keeps rising hazards across radio busy and the shared 8 s cooldown so edges are not dropped.
import {linePull} from '../tether/feel.js';

const HAZARDS = ['impact', 'snag', 'tension', 'battery', 'near'];

export function reactionSignals(state, previous) {
  const work = state.expedition?.active?.steps;
  const targets = work ? work.filter(step => !step.completed).slice(0, 1)
    : state.mission?.mode === 'inspection_coop' ? state.mission.targets || []
    : state.score?.objectives?.slice(state.score.current_index || 0, (state.score.current_index || 0) + 1)
      || state.mission?.targets || [];
  const near = targets.some(target => !target.done && !target.completed && target.point && state.pos &&
    Math.hypot(...target.point.map((value, axis) => value - state.pos[axis])) <= 2);
  const contact = state.events?.filter(hit => !hit.vehicle_id || hit.vehicle_id === state.vehicle_id).at(-1);
  return {
    impact: contact ? JSON.stringify([contact.t, contact.obstacle, contact.where]) : '',
    snag: !!state.tether?.snagged_on?.length ||
      Object.values(state.tether?.wraps || {}).some(turns => Math.abs(turns) >= 0.5),
    tension: linePull(state.tether, previous?.tension),
    battery: state.power?.type !== 'tether' && Number.isFinite(state.battery) && state.battery <= 20,
    near,
    progress: JSON.stringify([state.score?.current_index, state.photos, state.locked, state.keep_depth,
      state.rc?.right_switch, state.campaign?.index, state.mission?.completed, state.recording, state.tether?.broken])
  };
}

function keepPending(pending, signals, spoken) {
  return pending.filter(key => key !== spoken && signals[key]);
}

export function advanceReactions(previous, state, options = {}) {
  const {enabled = true, idle = true, mission = '', busy = false, now = state.t} = options;
  if ((!enabled && !idle) || !mission || state.paused || state.score?.finished || state.score?.failed) return null;
  const time = now;
  const signals = reactionSignals(state, previous?.signals);
  const initial = !previous || state.t < previous.simTime || mission !== previous.mission;
  if (initial) {
    return {
      simTime: state.t, mission, signals, activity: time, idleCount: 0, last: {}, next: time,
      pending: [], line: null
    };
  }
  const rising = HAZARDS.filter(function changed(key) {
    return signals[key] && signals[key] !== previous.signals[key];
  });
  const pending = [...new Set([...(previous.pending || []), ...rising])];
  const activity = busy || rising.length || signals.progress !== previous.signals.progress
    ? time : previous.activity;
  let line = null;
  if (!busy && time >= previous.next) {
    if (enabled) {
      line = pending.find(key => time - (previous.last[key] ?? -Infinity) >= 30) || null;
    }
    if (!line && idle && time - activity >= 45) line = 'idle';
  }
  return {
    simTime: state.t,
    mission,
    signals,
    line,
    activity: line ? time : activity,
    idleCount: previous.idleCount + (line === 'idle' ? 1 : 0),
    next: line ? time + 8 : previous.next,
    last: line ? {...previous.last, [line]: time} : previous.last,
    pending: keepPending(pending, signals, line)
  };
}
