// Pure state-to-sound mappings; no browser or audio resources are needed.
// Topside cues mirror what a pilot hears at the control box; underwater cues exceed a real vehicle.

export function clamp(value, low = 0, high = 1) {
  return Math.max(low, Math.min(high, Number.isFinite(value) ? value : low));
}

export function motorParameters(output) {
  const speed = clamp(Math.abs(output));
  return {
    frequency: 45 + 190 * Math.sqrt(speed),
    gain: speed * speed * 0.045,
    type: output < 0 ? 'triangle' : 'sawtooth'
  };
}

export function depthCutoff(depth) {
  return 250 + 2750 * Math.exp(-clamp(depth, 0, 1000) / 18);
}

// Continuous topside mechanical levels from tether.reel and ambient deck noise (assumptions; see research notes).
export function reelParameters(reel) {
  if (!reel || typeof reel !== 'object') {
    return {mode: null, speed: 0, motorGain: 0, motorHz: 55, brakeGain: 0, fairleadGain: 0};
  }
  const speed = Math.abs(Number(reel.speed) || 0);
  const mode = reel.mode || 'free';
  const moving = speed > 0.01;
  const powered = mode === 'pay_out' || mode === 'haul_in' || mode === 'auto';
  const motorGain = powered && moving ? clamp(speed / 0.8) * 0.2 : 0;
  const brakeGain = mode === 'hold' ? 0.045 : reel.stalled ? 0.09 : 0;
  const fairleadGain = moving ? clamp(speed / 0.55) * 0.12 : 0;
  return {
    mode,
    speed,
    motorGain,
    motorHz: 55 + speed * 95,
    brakeGain,
    fairleadGain
  };
}

export function topsideAmbience() {
  return {fanGain: 0.03, deckGain: 0.045};
}

const UNDERWATER_EVENTS = new Set(['touch', 'hard', 'severe', 'life']);

export function eventLayer(event) {
  return UNDERWATER_EVENTS.has(event) ? 'underwater' : 'topside';
}

// Maps a detected edge to a short cue kind and which mix bus layer may play it.
export function resolveCue(event, state) {
  if (event === 'locked' || event === 'keep_depth') {
    return {kind: state?.[event] ? 'confirm' : 'back', layer: 'topside'};
  }
  if (UNDERWATER_EVENTS.has(event)) {
    return {kind: event, layer: 'underwater'};
  }
  const kinds = {
    warn: 'warn',
    broken: 'broken',
    light: 'confirm',
    complete: 'complete',
    photos: 'photos',
    record_start: 'record',
    record_stop: 'back',
    link_lost: 'broken',
    link_degraded: 'warn',
    link_restored: 'confirm',
    dvl_lost: 'warn',
    dvl_locked: 'confirm',
    power_trip: 'broken',
    power_cutoff: 'broken',
    power_limited: 'warn',
    leak: 'broken',
    thermal: 'warn'
  };
  return {kind: kinds[event] || event, layer: 'topside'};
}

function eventKey(event) {
  return JSON.stringify([event.t, event.severity, event.obstacle, event.where]);
}

function pushUnique(events, name) {
  if (!events.includes(name)) events.push(name);
}

function dvlStatus(state) {
  return state?.sensors?.dvl?.status || null;
}

function linkState(state) {
  return state?.link?.state || null;
}

function thermalSet(state) {
  return new Set(state?.thermal?.warnings || []);
}

// Rising edges only. Rewound or first snapshots stay silent so replay seeks do not spam.
export function detectEvents(previous, state) {
  if (!previous || state.t < previous.t || state.vehicle_id !== previous.vehicle_id) return [];
  const events = [];
  for (const key of ['locked', 'keep_depth', 'photos']) {
    if (state[key] !== previous[key]) events.push(key);
  }
  if (!!state.recording !== !!previous.recording) {
    events.push(state.recording ? 'record_start' : 'record_stop');
  }
  if (state.rc?.right_switch !== previous.rc?.right_switch) events.push('light');
  for (const key of ['warn', 'broken']) {
    if (state.tether?.[key] && !previous.tether?.[key]) events.push(key);
  }
  if (state.score?.finished && !previous.score?.finished) events.push('complete');
  if (state.battery <= 20 && previous.battery > 20) pushUnique(events, 'warn');

  const prevLink = linkState(previous);
  const nextLink = linkState(state);
  if (nextLink === 'lost' && prevLink !== 'lost') events.push('link_lost');
  else if (nextLink === 'degraded' && prevLink === 'healthy') events.push('link_degraded');
  else if (nextLink === 'healthy' && prevLink && prevLink !== 'healthy') events.push('link_restored');

  const prevDvl = dvlStatus(previous);
  const nextDvl = dvlStatus(state);
  if (nextDvl === 'lost' && prevDvl && prevDvl !== 'lost') events.push('dvl_lost');
  else if (nextDvl === 'locked' && prevDvl === 'lost') events.push('dvl_locked');

  if (state.power?.tripped && !previous.power?.tripped) events.push('power_trip');
  if (state.power?.cutoff && !previous.power?.cutoff) events.push('power_cutoff');
  if (state.power?.limited && !previous.power?.limited) events.push('power_limited');
  if (state.leak?.detected && !previous.leak?.detected) events.push('leak');

  const beforeThermal = thermalSet(previous);
  for (const code of thermalSet(state)) {
    if (!beforeThermal.has(code)) {
      pushUnique(events, 'thermal');
      break;
    }
  }

  const known = new Set((previous.events || []).map(eventKey));
  for (const event of state.events || []) {
    if (!known.has(eventKey(event))) events.push(event.severity);
  }
  return events;
}

// Which continuous buses a fidelity setting should drive this frame.
export function layerGains(underwaterEnabled) {
  return {
    topside: 1,
    underwater: underwaterEnabled ? 1 : 0
  };
}
