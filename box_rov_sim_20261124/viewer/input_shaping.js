// Gamepad input shaping for ROV-01 (Wave 2): radial deadzone + expo curve.
// Mirrored 1:1 with rov01sim/input_shaping.py (parity tested in tests/test_wave2.py).

export const DEADZONE_MAX = 0.45;
export const DEFAULT_DEADZONE = 0.08;
export const DEFAULT_EXPO = 0.35;

function num(v, d) {
  if (v === null || v === undefined || v === "" || typeof v === "boolean" || typeof v === "object") return d;
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
}

function clamp(v, lo, hi) {
  const n = num(v, 0);
  return n < lo ? lo : n > hi ? hi : n;
}

export function sanitize(deadzone = DEFAULT_DEADZONE, expo = DEFAULT_EXPO) {
  return [
    clamp(num(deadzone, DEFAULT_DEADZONE), 0, DEADZONE_MAX),
    clamp(num(expo, DEFAULT_EXPO), 0, 1),
  ];
}


let _currentDeadzone = DEFAULT_DEADZONE;
let _currentExpo = DEFAULT_EXPO;

export function setShaping(opts = {}) {
  const dzIn = opts && typeof opts === "object" && "deadzone" in opts ? opts.deadzone : _currentDeadzone;
  const exIn = opts && typeof opts === "object" && "expo" in opts ? opts.expo : _currentExpo;
  const [dz, ex] = sanitize(dzIn, exIn);
  _currentDeadzone = dz;
  _currentExpo = ex;
  return { deadzone: _currentDeadzone, expo: _currentExpo };
}

export function getShaping() {
  return { deadzone: _currentDeadzone, expo: _currentExpo };
}

export function expoCurve(u, expo) {
  const uc = clamp(num(u, 0), 0, 1);
  const ex = clamp(num(expo, DEFAULT_EXPO), 0, 1);
  return clamp((1 - ex) * uc + ex * uc * uc * uc, 0, 1);
}

export function radialDeadzoneExpo(x, y, deadzone = DEFAULT_DEADZONE, expo = DEFAULT_EXPO) {
  const [dz, ex] = sanitize(deadzone, expo);
  x = clamp(num(x, 0), -1, 1);
  y = clamp(num(y, 0), -1, 1);
  const r = Math.hypot(x, y);
  if (!Number.isFinite(r) || r <= dz || r === 0) return [0, 0];
  const rc = Math.min(r, 1);
  const u = (rc - dz) / Math.max(1e-9, 1 - dz);
  const scale = expoCurve(u, ex) / r;
  return [clamp(x * scale, -1, 1), clamp(y * scale, -1, 1)];
}

export function axisDeadzoneExpo(v, deadzone = DEFAULT_DEADZONE, expo = DEFAULT_EXPO) {
  return radialDeadzoneExpo(v, 0, deadzone, expo)[0];
}

export function shapeStick2d(x, y, deadzone = DEFAULT_DEADZONE, expo = DEFAULT_EXPO) {
  return radialDeadzoneExpo(x, y, deadzone, expo);
}

export function shapeGamepad6Dof(rawAxes, deadzone = DEFAULT_DEADZONE, expo = DEFAULT_EXPO) {
  const src = rawAxes && typeof rawAxes === "object" && !Array.isArray(rawAxes) ? rawAxes : {};
  const [dz, ex] = sanitize(deadzone, expo);
  const out = {};
  for (const k of ["surge", "sway", "heave", "roll", "pitch", "yaw"]) {
    out[k] = Number(axisDeadzoneExpo(src[k], dz, ex).toFixed(6));
  }
  return out;
}

const ROVInputShaping = {
  DEADZONE_MAX,
  DEFAULT_DEADZONE,
  DEFAULT_EXPO,
  sanitize,
  expoCurve,
  radialDeadzoneExpo,
  axisDeadzoneExpo,
  setShaping,
  getShaping,
  shapeStick2d,
  shapeGamepad6Dof,
};

if (typeof window !== "undefined") {
  window.ROVInputShaping = ROVInputShaping;
}

export default ROVInputShaping;
