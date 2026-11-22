// New-player onboarding, without the DOM: which basic step the pilot should learn next, when a step counts as done
// and which first-time tip an event calls for. Every check reads the received simulator state (the same telemetry
// the HUD shows), so a hint can never claim something the vehicle did not do. Progress is stored per browser profile
// (localStorage) and survives later dives; the settings can turn the hints off or show them again from the start.
// The hints teach this game's own controls and the steps a trainer beside a real pilot would talk through; they
// reveal nothing a real pilot's console does not show, so they are interface help, not a fidelity item.
import { axisChannel } from '../input/bindings.js';

export const ONBOARDING_KEY = 'rov.onboarding.v1';
// Dispatched on document when the settings change the stored progress, so a running dive reloads it.
export const ONBOARDING_CHANGED = 'rov-onboarding-changed';
// The basic steps in teaching order. `move` has three parts (MOVES) that tick off one by one.
export const STEPS = ['unlock', 'move', 'depth', 'light', 'photo', 'objectives', 'pause'];
export const MOVES = ['surge', 'yaw', 'heave'];
// First-time tips, shown once when their event happens (ahead of the step hint).
export const TIPS = ['tether', 'dvl', 'visibility'];
// A stick channel counts as used after this much commanded time while the vehicle is unlocked.
export const MOVE_SECONDS = 0.8;
const STICK_DEADBAND = 80;
const LOW_VISIBILITY_M = 1.5;
const HEAVY_SILT = 0.6;

function storage(store) {
  if (store !== undefined) return store;
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

function flags(source, names) {
  const result = {};
  for (const name of names) result[name] = !!source?.[name];
  return result;
}

// Stored progress: {enabled, steps, moves, tips}; unknown or broken records start fresh.
export function loadProgress(store) {
  let saved = {};
  try {
    saved = JSON.parse(storage(store)?.getItem(ONBOARDING_KEY) || '{}') || {};
  } catch {
    saved = {};
  }
  return {
    enabled: saved.enabled !== false,
    steps: flags(saved.steps, STEPS),
    moves: flags(saved.moves, MOVES),
    tips: flags(saved.tips, TIPS),
  };
}

export function saveProgress(progress, store) {
  try {
    storage(store)?.setItem(ONBOARDING_KEY, JSON.stringify(progress));
  } catch {
    // Private windows may refuse storage; the hints then simply show again next time.
  }
}

// Forget every completed step and tip (settings: 重新顯示新手提示). The hints are switched back on as well.
export function resetProgress(store) {
  const fresh = { enabled: true, steps: flags({}, STEPS), moves: flags({}, MOVES), tips: flags({}, TIPS) };
  saveProgress(fresh, store);
  return fresh;
}

// The first basic step not yet done, or null when the pilot has learnt them all.
export function currentStep(progress) {
  return STEPS.find(function open(step) {
    return !progress.steps[step];
  }) || null;
}

export function stepsDone(progress) {
  return STEPS.filter(function done(step) {
    return progress.steps[step];
  }).length;
}

// Transient per-dive observations that decide completion (baselines, commanded stick time).
export function createTracker() {
  return { lastT: null, photos: null, depth: null, depthChanged: false, stick: {} };
}

function stickDeflected(state, axis, mode) {
  const drive = axisChannel(axis, mode);
  const value = drive ? state.rc?.[drive.channel] : undefined;
  return typeof value === 'number' && Math.abs(value - 1500) > STICK_DEADBAND;
}

function complete(progress, done, group, name) {
  if (progress[group][name]) return;
  progress[group][name] = true;
  done.push(group === 'steps' ? name : `${group}:${name}`);
}

function observeMoves(progress, tracker, state, dt, mode, done) {
  for (const axis of MOVES) {
    if (!stickDeflected(state, axis, mode)) continue;
    tracker.stick[axis] = (tracker.stick[axis] || 0) + dt;
    if (tracker.stick[axis] >= MOVE_SECONDS) complete(progress, done, 'moves', axis);
  }
  if (MOVES.every((axis) => progress.moves[axis])) complete(progress, done, 'steps', 'move');
}

// The pilot's depth-hold switch (the RC echo), not the vehicle's hold state, which the simulator may drop by itself.
function depthSwitch(state) {
  return !!(state.rc?.keep_depth ?? state.keep_depth);
}

function observeDepth(progress, tracker, state, done) {
  const on = depthSwitch(state);
  // Until the pilot first unlocks, the switch follows the launch defaults and resynchronisation, not the pilot.
  if (tracker.depth === null || state.locked !== false) tracker.depth = on;
  if (on !== tracker.depth) tracker.depthChanged = true;
  tracker.depth = on;
  // Done once the pilot has used the switch and depth hold is on again, so the lesson never leaves it off.
  if (tracker.depthChanged && on) complete(progress, done, 'steps', 'depth');
}

// Update progress from one received state. context: {pauseOpen, peekCard, operationMode}. Returns what was
// completed by this state (step ids, or `moves:<axis>`), so the caller can save and acknowledge it.
export function observe(progress, tracker, state, context = {}) {
  const done = [];
  if (!state) return done;
  const t = Number(state.t) || 0;
  const dt = tracker.lastT === null ? 0 : Math.max(0, Math.min(0.5, t - tracker.lastT));
  tracker.lastT = t;
  const photos = Number(state.photos) || 0;
  if (tracker.photos === null || photos < tracker.photos) tracker.photos = photos;
  // Opening the pause menu pauses a solo dive, so it counts before the paused check below.
  if (context.pauseOpen) complete(progress, done, 'steps', 'pause');
  if (state.paused || state.remote_control) return done;
  if (state.locked === false) complete(progress, done, 'steps', 'unlock');
  const mode = state.operation_mode || context.operationMode || 'ROV_USA';
  if (state.locked === false) observeMoves(progress, tracker, state, dt, mode, done);
  observeDepth(progress, tracker, state, done);
  if ((state.rc?.right_switch ?? 0) > 0) complete(progress, done, 'steps', 'light');
  if (photos > tracker.photos) complete(progress, done, 'steps', 'photo');
  tracker.photos = photos;
  if (context.peekCard === 0) complete(progress, done, 'steps', 'objectives');
  return done;
}

// Whether a tip's event is happening in this state.
export function tipActive(tip, state) {
  if (!state) return false;
  if (tip === 'tether') return !!state.tether?.warn && !state.tether?.broken;
  // The DVL only matters to the pilot while an assist that needs it is asked for (hud/assist_pill.js).
  if (tip === 'dvl') return state.sensors?.dvl?.status === 'lost' && (state.rc?.assist ?? state.assist?.level ?? 0) > 0;
  if (tip === 'visibility') {
    const visibility = state.turbidity?.visibility_m;
    return (typeof visibility === 'number' && visibility < LOW_VISIBILITY_M) || (state.silt ?? 0) > HEAVY_SILT;
  }
  return false;
}

// The first tip whose event is happening and that this profile has not seen yet, or null.
export function pendingTip(progress, state, step = null) {
  return TIPS.find(function due(tip) {
    // Above a sloping reef the DVL can lose bottom before the pilot first unlocks. Its assist starts on unlock.
    if (tip === 'dvl' && step === 'unlock' && state?.locked) return false;
    return !progress.tips[tip] && tipActive(tip, state);
  }) || null;
}
