// Trailer camera paths: Catmull-Rom keyframe interpolation for follow / orbit / fixed / onboard.
// Pure functions with no DOM; node --test loads this module directly.

const MODES = Object.freeze(['follow', 'orbit', 'fixed', 'onboard']);

/** Uniform Catmull-Rom between p1 and p2; t in [0, 1]. Endpoints are extrapolated by repetition. */
export function catmullRom(p0, p1, p2, p3, t) {
  const t2 = t * t;
  const t3 = t2 * t;
  const out = new Array(p1.length);
  for (let i = 0; i < p1.length; i++) {
    const a = p0[i];
    const b = p1[i];
    const c = p2[i];
    const d = p3[i];
    out[i] = 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3);
  }
  return out;
}

function clamp(value, lo, hi) {
  return Math.max(lo, Math.min(hi, value));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

/** Pick the segment that contains time `t` (seconds from shot start). */
export function segmentIndex(times, t) {
  if (!times.length) return 0;
  if (t <= times[0]) return 0;
  for (let i = 0; i < times.length - 1; i++) {
    if (t <= times[i + 1]) return i;
  }
  return Math.max(0, times.length - 2);
}

function pointAt(keyframes, attr, index) {
  const frame = keyframes[clamp(index, 0, keyframes.length - 1)];
  return frame[attr];
}

/** Interpolate a vector attribute across keyframes with Catmull-Rom.
 *  Returns null when any keyframe omits the attribute so callers can use defaults
 *  (lookAt / lookOffset / offset are optional in storyboards). */
export function interpolateVector(keyframes, attr, t) {
  if (!keyframes.length) return null;
  if (!keyframes.every((frame) => Array.isArray(frame[attr]))) return null;
  if (keyframes.length === 1) return pointAt(keyframes, attr, 0).slice();
  const times = keyframes.map((frame) => frame.t);
  const i = segmentIndex(times, t);
  const t0 = times[i];
  const t1 = times[Math.min(i + 1, times.length - 1)];
  const u = t1 > t0 ? clamp((t - t0) / (t1 - t0), 0, 1) : 0;
  const p0 = pointAt(keyframes, attr, i - 1);
  const p1 = pointAt(keyframes, attr, i);
  const p2 = pointAt(keyframes, attr, i + 1);
  const p3 = pointAt(keyframes, attr, i + 2);
  return catmullRom(p0, p1, p2, p3, u);
}

/** Interpolate a scalar attribute with Catmull-Rom (1-D). */
export function interpolateScalar(keyframes, attr, t, fallback) {
  if (!keyframes.length) return fallback;
  const series = keyframes.map((frame) => ({
    t: frame.t,
    v: [frame[attr] == null ? fallback : frame[attr]],
  }));
  const times = series.map((frame) => frame.t);
  const i = segmentIndex(times, t);
  const t0 = times[i];
  const t1 = times[Math.min(i + 1, times.length - 1)];
  const u = t1 > t0 ? clamp((t - t0) / (t1 - t0), 0, 1) : 0;
  const p0 = series[clamp(i - 1, 0, series.length - 1)].v;
  const p1 = series[i].v;
  const p2 = series[clamp(i + 1, 0, series.length - 1)].v;
  const p3 = series[clamp(i + 2, 0, series.length - 1)].v;
  return catmullRom(p0, p1, p2, p3, u)[0];
}

/**
 * Evaluate a camera path at shot-local time `t`.
 * `rov` is {position: [x,y,z], heading: radians} in three.js Y-up (x east-neg, y up-neg-down, z north).
 * Returns {mode, position, lookAt, fov} or null for onboard (caller keeps the rig).
 */
export function evaluateCameraPath(path, t, rov) {
  if (!path || !path.mode) return null;
  const mode = path.mode;
  if (!MODES.includes(mode)) {
    throw new Error(`unknown camera mode ${mode}`);
  }
  if (mode === 'onboard') return {mode, position: null, lookAt: null, fov: 70};
  const keyframes = path.keyframes || [];
  if (!keyframes.length) {
    throw new Error(`camera mode ${mode} needs keyframes`);
  }
  const fov = interpolateScalar(keyframes, 'fov', t, path.fov ?? 55);
  if (mode === 'fixed') {
    const position = interpolateVector(keyframes, 'position', t);
    const lookAt = interpolateVector(keyframes, 'lookAt', t) || rov.position.slice();
    return {mode, position, lookAt, fov};
  }
  if (mode === 'follow') {
    const offset = interpolateVector(keyframes, 'offset', t) || [0, 1.2, -3.5];
    const heading = rov.heading || 0;
    const cos = Math.cos(heading);
    const sin = Math.sin(heading);
    // offset is (right, up, back) in the ROV's horizontal heading frame.
    const world = [
      rov.position[0] + offset[0] * cos + offset[2] * sin,
      rov.position[1] + offset[1],
      rov.position[2] - offset[0] * sin + offset[2] * cos,
    ];
    const look = interpolateVector(keyframes, 'lookOffset', t) || [0, 0.2, 1.5];
    const lookAt = [
      rov.position[0] + look[0] * cos + look[2] * sin,
      rov.position[1] + look[1],
      rov.position[2] - look[0] * sin + look[2] * cos,
    ];
    return {mode, position: world, lookAt, fov};
  }
  // orbit: keyframes use azimuth (rad), radius, height (three.js y relative to ROV).
  const azimuth = interpolateScalar(keyframes, 'azimuth', t, 0);
  const radius = interpolateScalar(keyframes, 'radius', t, 4.5);
  const height = interpolateScalar(keyframes, 'height', t, 1.2);
  const position = [
    rov.position[0] + Math.cos(azimuth) * radius,
    rov.position[1] + height,
    rov.position[2] + Math.sin(azimuth) * radius,
  ];
  return {mode, position, lookAt: rov.position.slice(), fov};
}

/** Linear blend helper used by tests for non-spline sanity checks. */
export function lerpScalar(a, b, t) {
  return lerp(a, b, clamp(t, 0, 1));
}

export const CAMERA_MODES = MODES;
