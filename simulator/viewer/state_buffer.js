// Server-time snapshot sampling shared by live rendering and recorded playback.
// Callers that negotiated static_once must merge via state_merge.js before push();
// replay clips store complete snapshots and do not declare that capability.
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

export function slerp(a, b, k) {
  let dot = a.reduce((s, v, i) => s + v * b[i], 0);
  if (dot < 0) {
    b = b.map(v => -v);
    dot = -dot;
  }
  const angle = Math.acos(clamp(dot, -1, 1));
  const wa = angle < .001 ? 1 - k : Math.sin((1 - k) * angle) / Math.sin(angle);
  const wb = angle < .001 ? k : Math.sin(k * angle) / Math.sin(angle);
  const q = a.map((v, i) => v * wa + b[i] * wb);
  const length = Math.hypot(...q);
  return q.map(v => v / length);
}

function vector(a, b, k) {
  return a?.map((v, i) => v + ((b?.[i] ?? v) - v) * k);
}

function pose(a, b, k, extra = 0, previous = null) {
  const result = {...a};
  result.pos = vector(a.pos, b?.pos, k);
  if (a.vel) result.vel = vector(a.vel, b?.vel, k);
  if (a.q) result.q = b?.q ? slerp(a.q, b.q, k) : a.q.slice();
  if (extra && a.pos && a.vel) {
    let velocity = a.vel;
    if (a.q) {
      const [w, x, y, z] = a.q;
      const [vx, vy, vz] = velocity;
      velocity = [
        (1 - 2 * (y * y + z * z)) * vx + 2 * (x * y - w * z) * vy + 2 * (x * z + w * y) * vz,
        2 * (x * y + w * z) * vx + (1 - 2 * (x * x + z * z)) * vy + 2 * (y * z - w * x) * vz,
        2 * (x * z - w * y) * vx + 2 * (y * z + w * x) * vy + (1 - 2 * (x * x + y * y)) * vz
      ];
    }
    result.pos = a.pos.map((v, i) => v + velocity[i] * extra);
  }
  if (extra && a.q && previous?.q && a.t > previous.t) {
    const dot = Math.abs(previous.q.reduce((sum, v, i) => sum + v * a.q[i], 0));
    const angle = 2 * Math.acos(clamp(dot, -1, 1));
    const fraction = Math.min(extra / (a.t - previous.t), angle > 1e-9 ? extra * 8 / angle : 0);
    result.q = slerp(previous.q, a.q, 1 + fraction);
  }
  if (a.tether) {
    const nodes = a.tether.nodes;
    const next = b?.tether?.nodes;
    result.tether = {...a.tether, nodes: nodes?.map((v, i) =>
      vector(v, nodes.length === next?.length ? next[i] : v, k))};
  }
  return result;
}

function entities(a = [], b = [], k, extra, previous = []) {
  const targets = new Map(b.map(v => [v.id ?? v.vehicle_id, v]));
  const history = new Map(previous.map(v => [v.id ?? v.vehicle_id, v]));
  return a.map(v => pose(v, targets.get(v.id ?? v.vehicle_id), k, extra,
    history.get(v.id ?? v.vehicle_id)));
}

function renderFields(a, b, k, time, extra = 0, previous = null) {
  const result = pose(a, b, k, extra, previous);
  result.t = a.paused ? a.t : time;
  if (a.vehicles) {
    const history = previous?.vehicles?.map(v => ({...v, t: previous.t}));
    result.vehicles = entities(a.vehicles.map(v => ({...v, t: a.t})), b?.vehicles, k, extra, history);
  }
  if (a.operations?.objects) {
    result.operations = {...a.operations,
      objects: entities(a.operations.objects, b?.operations?.objects, k, extra)};
  }
  if (a.environment?.fish_schools) {
    result.environment = {...a.environment,
      fish_schools: entities(a.environment.fish_schools, b?.environment?.fish_schools, k, extra)};
  }
  return result;
}

export function sampleSnapshots(frames, time) {
  if (!frames.length) return null;
  if (time <= frames[0].t) return renderFields(frames[0], null, 0, time);
  let lo = 0;
  let hi = frames.length - 1;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (frames[mid].t < time) lo = mid;
    else hi = mid - 1;
  }
  const a = frames[lo];
  const b = frames[lo + 1];
  if (b) return renderFields(a, b, (time - a.t) / Math.max(.00001, b.t - a.t), time);
  const extra = a.paused ? 0 : Math.min(.1, Math.max(0, time - a.t));
  return renderFields(a, null, 0, time, extra, frames[lo - 1]);
}

export class StateBuffer {
  constructor() {
    this.reset();
  }
  reset() {
    this.frames = [];
    this.offset = null;
    this.interval = .05;
    this.jitter = 0;
    this.time = null;
    this.arrival = null;
    this.output = null;
    this.recoveryUntil = 0;
    this.sampledAt = null;
  }
  push(state, now = performance.now() / 1000) {
    if (!Number.isFinite(state.t)) return;
    const last = this.frames.at(-1);
    if (last && (state.t < last.t - .5 || (last.paused && !state.paused))) this.reset();
    const latest = this.frames.at(-1);
    if (!latest || state.t > latest.t) {
      if (latest) {
        const gap = state.t - latest.t;
        if (now - this.arrival > .15) this.recoveryUntil = now + .5;
        this.interval += .1 * (Math.min(.15, gap) - this.interval);
        this.jitter += .1 * (Math.abs(now - this.arrival - gap) - this.jitter);
      }
      const offset = now - state.t;
      this.offset = this.offset === null ? offset : this.offset + .05 * (offset - this.offset);
      this.arrival = now;
    }
    const duplicate = this.frames.findIndex(s => s.t === state.t);
    if (duplicate >= 0) {
      this.frames[duplicate] = state;
      return;
    }
    this.frames.push(state);
    this.frames.sort((a, b) => a.t - b.t);
    // Keep enough history for the simulated link's video lag (up to ~5 s at the 30 Hz state rate).
    if (this.frames.length > 300) this.frames.shift();
  }
  sample(now = performance.now() / 1000, local = false, delayOverride = null) {
    if (this.offset === null) return null;
    // Assisted view may look ahead half a packet; real mode supplies a positive delay override.
    const delay = delayOverride ?? (local ? -Math.min(.025, this.interval / 2) :
      clamp(2 * this.interval + 2 * this.jitter, .04, .25));
    const desired = now - this.offset - delay;
    // Never rewind when the adaptive delay increases.
    this.time = Math.max(this.time ?? desired, desired);
    const result = sampleSnapshots(this.frames, this.time);
    const step = Math.max(0, now - (this.sampledAt ?? now));
    function limitPose(value, previous) {
      if (!value?.pos || !previous?.pos) return;
      const distance = Math.hypot(...value.pos.map((v, i) => v - previous.pos[i]));
      const k = distance > 0 ? Math.min(1, 8 * step / distance) : 1;
      value.pos = value.pos.map((v, i) => previous.pos[i] + (v - previous.pos[i]) * k);
    }
    function limitEntities(values = [], previous = []) {
      const history = new Map(previous.map(v => [v.id ?? v.vehicle_id, v]));
      for (const value of values) limitPose(value, history.get(value.id ?? value.vehicle_id));
    }
    if (this.output && now < this.recoveryUntil) {
      limitPose(result, this.output);
      limitEntities(result.vehicles, this.output.vehicles);
      limitEntities(result.operations?.objects, this.output.operations?.objects);
      limitEntities(result.environment?.fish_schools, this.output.environment?.fish_schools);
    }
    this.output = result;
    this.sampledAt = now;
    return result;
  }
}

// Keep render-state selection and scene pose updates out of the shared app loop.
// `link` is the optional presenter from video_link.js; without it the simulated vehicle link is ignored.
export function createRenderState({P, Q, rovG, fleet, updateTether, params = new URLSearchParams(), fidelity = null,
  link = null}) {
  const legacyAssisted = params.get('presentation') === 'assisted';
  // Provisional generic video latency from the research report, not a vehicle-specific measurement.
  const configuredDelay = Number(params.get('videoDelayMs') ?? 150);
  const legacyDelay = clamp(Number.isFinite(configuredDelay) ? configuredDelay : 150, 0, 1000) / 1000;
  // With a fidelity store the delay is live; zero delay selects the low-latency predicted presentation.
  function presentation() {
    if (!fidelity) return {assisted: legacyAssisted, videoDelay: legacyDelay};
    const delay = fidelity.get('videoDelayMs') / 1000;
    return {assisted: delay <= 0, videoDelay: delay};
  }
  const remote = new StateBuffer();
  const local = new StateBuffer();
  let state = null;
  let linkReport = null;
  function linkNow() {
    return link && linkReport ? link.effect(linkReport) : null;
  }
  // What the operator learns only through the vehicle's own telemetry, which shares the video link.
  const ONBOARD_FIELDS = ['pos', 'q', 'euler', 'vel', 'speed_kn', 'thrust', 'battery', 'current_here',
    'current_kn', 'silt', 'tether', 'events', 'damage', 'vehicles', 'power',
    'thermal', 'leak', 'sensors'];
  // State for the onboard overlay and vehicle sounds: telemetry as old as the picture, while the
  // pilot's own switches, missions and room data stay current. Without a video delay it is `latest`.
  function display(latest) {
    const telemetry = link && latest ? link.telemetry(latest, linkNow(), performance.now() / 1000) : null;
    if (telemetry) {
      // A degraded or lost link delivers vehicle telemetry at its own (reduced or zero) rate.
      const held = {...latest};
      for (const field of ONBOARD_FIELDS) {
        if (field in telemetry) held[field] = telemetry[field];
      }
      return held;
    }
    if (!latest || !state || state === latest || presentation().assisted) return latest;
    const shown = {...latest};
    for (const field of ONBOARD_FIELDS) {
      if (field in state) shown[field] = state[field];
    }
    return shown;
  }
  function ingest(snapshot, replay, now) {
    if (replay) return;
    linkReport = snapshot.link ?? null;
    remote.push(snapshot, now);
    local.push(snapshot, now);
  }
  function update(snapshot, replay, now) {
    const {assisted, videoDelay} = presentation();
    const effect = replay ? null : linkNow();
    // A frozen link holds the last delivered picture: neither the pose nor the scene state moves.
    if (effect?.frozen && state) return;
    // Link lag is added to the video delay; it also overrides the predicted (assisted) presentation.
    const predicted = assisted && !effect;
    const delay = videoDelay + (effect?.extraDelay ?? 0);
    state = replay ? snapshot : remote.sample(now, false, predicted ? null : delay);
    const own = replay ? snapshot : predicted ? local.sample(now, true) : state;
    if (own) {
      P(own.pos, rovG.position);
      Q(own.q, rovG.quaternion);
    }
    if (state) {
      fleet.ingest(state);
      updateTether(state.tether || {});
    }
  }
  return {
    ingest,
    update,
    display,
    get state() {
      return state;
    },
    get linkEffect() {
      return linkNow();
    }
  };
}
