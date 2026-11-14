// Server-time snapshot sampling shared by live rendering and recorded playback.
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

function blend(a, b, k, key = '') {
  if (a == null || b == null) return a;
  if (key === 'q' && Array.isArray(a)) return slerp(a, b, k);
  if (Array.isArray(a)) {
    if (a.length !== b.length) return a;
    return a.map((v, i) => blend(v, b[i], k, key));
  }
  if (typeof a === 'object') {
    if (a.id !== b.id) return a;
    return Object.fromEntries(Object.keys(a).map(name => [name, blend(a[name], b[name], k, name)]));
  }
  if (typeof a === 'number' && ['pos', 'nodes', 't', 'vel'].includes(key)) return a + (b - a) * k;
  return a;
}

export function sampleSnapshots(frames, time) {
  if (!frames.length) return null;
  if (time <= frames[0].t) return {...frames[0], t: time};
  for (let i = 1; i < frames.length; i++) {
    if (frames[i].t >= time) {
      const a = frames[i - 1], b = frames[i];
      return blend(a, b, (time - a.t) / Math.max(.00001, b.t - a.t));
    }
  }
  const last = frames.at(-1);
  const extra = last.paused ? 0 : Math.min(.1, Math.max(0, time - last.t));
  const result = structuredClone(last);
  function predict(value) {
    if (!value || typeof value !== 'object') return;
    if (value.pos && value.vel) {
      let velocity = value.vel;
      if (value.q) {
        const [w, x, y, z] = value.q;
        const [vx, vy, vz] = velocity;
        velocity = [
          (1 - 2 * (y * y + z * z)) * vx + 2 * (x * y - w * z) * vy + 2 * (x * z + w * y) * vz,
          2 * (x * y + w * z) * vx + (1 - 2 * (x * x + z * z)) * vy + 2 * (y * z - w * x) * vz,
          2 * (x * z - w * y) * vx + 2 * (y * z + w * x) * vy + (1 - 2 * (x * x + y * y)) * vz
        ];
      }
      value.pos = value.pos.map((v, i) => v + velocity[i] * extra);
    }
    for (const [key, child] of Object.entries(value)) if (key !== 'pos') predict(child);
  }
  predict(result);
  result.t = last.paused ? last.t : time;
  return result;
}

export class StateBuffer {
  constructor() { this.reset(); }
  reset() {
    this.frames = [];
    this.offset = null;
    this.interval = .05;
    this.jitter = 0;
    this.time = null;
    this.arrival = null;
    this.output = null;
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
        this.interval += .1 * (Math.min(.15, gap) - this.interval);
        this.jitter += .1 * (Math.abs(now - this.arrival - gap) - this.jitter);
      }
      const offset = now - state.t;
      this.offset = this.offset === null ? offset : this.offset + .05 * (offset - this.offset);
      this.arrival = now;
    }
    if (this.frames.some(s => s.t === state.t)) return;
    this.frames.push(state);
    this.frames.sort((a, b) => a.t - b.t);
    if (this.frames.length > 90) this.frames.shift();
  }
  sample(now = performance.now() / 1000, local = false) {
    if (this.offset === null) return null;
    const delay = local ? 0 : clamp(2 * this.interval + 2 * this.jitter, .04, .25);
    const desired = now - this.offset - delay;
    // Never rewind when the adaptive delay increases.
    this.time = Math.max(this.time ?? desired, desired);
    const result = sampleSnapshots(this.frames, this.time);
    const step = Math.max(0, now - (this.sampledAt ?? now));
    function limit(value, previous) {
      if (!value || !previous || typeof value !== 'object') return;
      if (value.id !== previous.id) return;
      if (value.pos && previous.pos) {
        const distance = Math.hypot(...value.pos.map((v, i) => v - previous.pos[i]));
        const k = distance > 0 ? Math.min(1, 8 * step / distance) : 1;
        value.pos = value.pos.map((v, i) => previous.pos[i] + (v - previous.pos[i]) * k);
      }
      for (const key of Object.keys(value)) if (key !== 'pos') limit(value[key], previous[key]);
    }
    if (this.output) limit(result, this.output);
    this.output = structuredClone(result);
    this.sampledAt = now;
    return result;
  }
}
