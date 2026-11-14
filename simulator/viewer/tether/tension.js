// Tether tension colours and gauge marks against the host's rated working loads (state.tether.working_load_n,
// gland_working_load_n). Older hosts without those fields keep the former fixed 250 N warning level.
import * as THREE from 'three';

export const LEGACY_WARN_N = 250;
export const BREAK_N = 300 * 9.80665;          // gauge full scale: X1 cable breaking strength (tether.py breaking_n)

const colLow = new THREE.Color('#e9c534');
const colWarn = new THREE.Color('#ffb020');
const colBreak = new THREE.Color('#ff3040');

function clamp01(value) {
  return Math.min(1, Math.max(0, value));
}

// Warning level for a tension field: the termination's working load at the vehicle end, the cable's elsewhere.
export function warnLoad(tether, key = 'tension_max') {
  const cable = tether?.working_load_n ?? LEGACY_WARN_N;
  if (key === 'tension_rov') return tether?.gland_working_load_n ?? cable;
  return cable;
}

export function tensionColor(T, out, warnN = LEGACY_WARN_N) {
  if (T <= warnN) return out.copy(colLow).lerp(colWarn, Math.pow(clamp01(T / warnN), 1.6));
  return out.copy(colWarn).lerp(colBreak, clamp01((T - warnN) / Math.max(BREAK_N - warnN, 1)) ** .6);
}

// Gauge fill fraction in percent (square-root scale up to the breaking strength).
export function gaugePercent(T) {
  return Math.sqrt(clamp01(T / BREAK_N)) * 100;
}
