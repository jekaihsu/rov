// Silt optics math shared by the renderer, the observation check and the optics pipeline.
// Pure functions with no imports (unit-tested from Node). Mirrors qysim/silt.py and PROTOCOL.md §4a:
// concentration C (mg/L = g/m³) from the server's Gaussian puffs plus the optional near-bed turbid layer,
// beam attenuation c = 4.8 / visibility_m + k·C and black-target visibility 4.8 / c (no floor).
// Positions are NED metres [north, east, down]. All coefficients are provisional (silt-validation.md).

export const SILT_OPTICS = Object.freeze({
  contrast: 4.8,          // visibility = 4.8 / c (Zaneveld & Pegau 2003)
  defaultK: 0.5,          // m²/g mass-specific attenuation when the server does not send one
  backscatterPerMgL: 0.06 // veil growth per mg/L in front of a lamp at full power (provisional, visual)
});

function finiteOr(value, fallback) {
  return Number.isFinite(value) ? value : fallback;
}

// Seabed depth under a point: a number, a function (n, e) => depth, or 30 m.
function bedAt(seabed, north, east) {
  if (typeof seabed === 'function') return seabed(north, east);
  return finiteOr(seabed, 30);
}

// Suspended concentration (mg/L) from the puff list [[n, e, d, sigmaH, sigmaV, peakMgL], ...].
export function puffConcentration(puffs, point, seabed) {
  if (!Array.isArray(puffs) || !puffs.length) return 0;
  const [n, e, d] = point;
  if (d > bedAt(seabed, n, e) + 1e-6) return 0;
  let total = 0;
  for (const puff of puffs) {
    const [pn, pe, pd, sh, sv, peak] = puff;
    const horizontal = ((n - pn) ** 2 + (e - pe) ** 2) / (2 * sh * sh);
    if (horizontal > 18) continue;
    const imageDepth = 2 * bedAt(seabed, pn, pe) - pd;
    const vertical = Math.exp(-((d - pd) ** 2) / (2 * sv * sv)) + Math.exp(-((d - imageDepth) ** 2) / (2 * sv * sv));
    total += peak * Math.exp(-horizontal) * vertical;
  }
  return total;
}

// Near-bed turbid layer: bnl_mg_l · exp(−altitude / bnl_height_m).
export function backgroundConcentration(turbidity, point, seabed) {
  const height = turbidity?.bnl_height_m || 0;
  const atBed = turbidity?.bnl_mg_l || 0;
  if (height <= 0 || atBed <= 0) return 0;
  const altitude = bedAt(seabed, point[0], point[1]) - point[2];
  if (altitude < -1e-6) return 0;
  return atBed * Math.exp(-Math.max(0, altitude) / height);
}

export function siltConcentration(environment, point, seabed) {
  const puffs = environment?.silt_puffs;
  return puffConcentration(puffs, point, seabed) + backgroundConcentration(environment?.turbidity, point, seabed);
}

// Beam attenuation c (1/m) at a point.
export function siltExtinction(environment, point, {visibilityM = 12, seabed} = {}) {
  const k = finiteOr(environment?.turbidity?.k_m2_per_g, SILT_OPTICS.defaultK);
  const water = SILT_OPTICS.contrast / Math.max(0.05, visibilityM);
  return water + k * siltConcentration(environment, point, seabed);
}

// Integrated optical depth along a → b (trapezoid rule).
export function siltOpticalDepth(environment, a, b, {visibilityM = 12, seabed, samples = 16} = {}) {
  const length = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
  if (!(length > 0)) return 0;
  const count = Math.max(2, samples);
  let sum = 0;
  for (let i = 0; i < count; i++) {
    const t = i / (count - 1);
    const p = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
    const weight = i === 0 || i === count - 1 ? 0.5 : 1;
    sum += weight * siltExtinction(environment, p, {visibilityM, seabed});
  }
  return sum * length / (count - 1);
}

// Optics at a point: concentration, attenuation, visibility and the sediment share of attenuation.
export function siltOpticsAt(environment, point, {visibilityM = 12, seabed} = {}) {
  const k = finiteOr(environment?.turbidity?.k_m2_per_g, SILT_OPTICS.defaultK);
  const mgL = siltConcentration(environment, point, seabed);
  const water = SILT_OPTICS.contrast / Math.max(0.05, visibilityM);
  const c = water + k * mgL;
  return {mgL, c, visibility: SILT_OPTICS.contrast / c, share: (k * mgL) / c};
}

// Lamp veil (0..1): grows with suspended sediment and lamp power. A camera within half a metre of the lamps
// (onboard) sees the full veil; farther away it fades with the attenuation between camera and lamps.
export function lampBackscatter(mgL, lampLevel, cameraToLampM = 0, attenuation = 0) {
  if (!(lampLevel > 0) || !(mgL > 0)) return 0;
  const veil = 1 - Math.exp(-SILT_OPTICS.backscatterPerMgL * mgL);
  const separation = Math.max(0, cameraToLampM - 0.5);
  return Math.min(1, veil * lampLevel * Math.exp(-attenuation * separation));
}

// Visibility used by assisted presentation: a floor of 25 % of base (only when the fidelity item allows it).
export function presentedVisibility(visibility, baseVisibility, floorEnabled) {
  if (!floorEnabled) return visibility;
  return Math.max(visibility, 0.25 * baseVisibility);
}
