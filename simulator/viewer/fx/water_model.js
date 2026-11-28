// Water optics model: per-channel (R, G, B) coefficients from the scenario's visibility and silt.
// Pure functions without imports so node tests can load the module directly.
//
// Model (an approximation of Akkaynak & Treibitz's point that attenuation is per channel and that the
// coefficient governing backscatter differs from the one governing the direct signal; see
// docs/reference/real-rov-research.md, "色彩沿整條光路流失"):
//   c  beam attenuation (direct signal, object -> camera and lamp -> object), per channel
//   b  scattering (spectrally flat suspended particles); drives in-scatter / backscatter
//   Kd diffuse attenuation of daylight from the surface down to a point, per channel
// Every number here is a visualization assumption (no measured water type or X1 data); see fx/README.md.

// Pure-water absorption representative of roughly 620 / 540 / 470 nm, 1/m (textbook order of magnitude).
export const PURE_WATER_ABSORPTION = Object.freeze([0.33, 0.06, 0.02]);
// Horizontal visibility of a dark target: V ~ 4.8 / c (contrast threshold of about 1 %). The silt module
// (feat/silt) uses the same relation, so a visibility and an attenuation coefficient convert both ways.
export const VISIBILITY_CONTRAST = 4.8;
// Share of the non-water attenuation that is scattering; the rest is particulate / dissolved absorption.
const SCATTER_SHARE = 0.8;
// Dissolved and particulate absorption rises towards blue (yellow substance); silt tints it further.
const PARTICLE_ABSORPTION_SPECTRUM = Object.freeze([0.6, 1.0, 1.7]);
const SILT_ABSORPTION_SPECTRUM = Object.freeze([0.0, 0.25, 0.9]);
// Optical water types (world.scenario.water_type), loosely after Jerlov's classes. Each adds coloured dissolved
// organic matter and detritus ("yellow substance") absorption, a_g(440 nm) in 1/m, which takes blue first and so
// turns the water from blue (oceanic) through green (shelf) to yellow-green (harbour). Assumed per class from
// the order of magnitude of open-ocean, coastal and estuarine values; not site measurements.
export const WATER_TYPES = Object.freeze({
  oceanic: 0.015,
  coastal: 0.08,
  shelf: 0.2,
  harbour: 0.35,
  fresh_clear: 0.0
});
// a_g(lambda) = a_g(440) exp(-0.015 (lambda - 440)) at the three band centres (620 / 540 / 470 nm).
const YELLOW_SUBSTANCE_SPECTRUM = Object.freeze([0.067, 0.223, 0.638]);
const MIN_VISIBILITY_M = 0.3;
const MAX_VISIBILITY_M = 80;

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

// Returns {c, b, a, kd} (arrays of three, 1/m) for a horizontal visibility in metres, silt 0..1 and an optional
// water type. The green channel's beam attenuation is tied to visibility, so distant objects vanish at that
// range; the yellow substance of the water type comes out of the same budget (a very clear visibility in
// shelf water is therefore capped by the water itself). Unknown or missing type: no yellow substance.
export function waterCoefficients(visibility, silt = 0, type = null) {
  const range = clamp(Number(visibility) || 12, MIN_VISIBILITY_M, MAX_VISIBILITY_M);
  const cloud = clamp(Number(silt) || 0, 0, 1);
  const yellow = WATER_TYPES[type] ?? 0;
  const green = VISIBILITY_CONTRAST / range;
  const rest = Math.max(0.01, green - PURE_WATER_ABSORPTION[1] - yellow * YELLOW_SUBSTANCE_SPECTRUM[1]);
  // Shelf haze includes suspended mineral grains. Their grey absorption can grow with
  // turbidity without treating all additional extinction as blue-absorbing organic matter.
  const shelf = type === 'shelf';
  const b = (shelf ? 0.92 : SCATTER_SHARE) * rest;
  const particleAbsorption = rest - b;
  const colouredAbsorption = shelf ? Math.min(0.025, particleAbsorption) : particleAbsorption;
  // A turbid shelf station measures local horizontal contrast. For downwelling light
  // approximate the clearer overlying column with at most 0.5/m non-water extinction.
  const columnFraction = shelf ? Math.min(1, 0.5 / rest) : 1;
  const a = [];
  const c = [];
  const kd = [];
  for (let i = 0; i < 3; i++) {
    const spectrum = PARTICLE_ABSORPTION_SPECTRUM[i] + cloud * SILT_ABSORPTION_SPECTRUM[i];
    a[i] = PURE_WATER_ABSORPTION[i] + yellow * YELLOW_SUBSTANCE_SPECTRUM[i]
      + particleAbsorption + colouredAbsorption * (spectrum - 1);
    c[i] = a[i] + b;
    // Diffuse light is mostly absorbed on the way down; only a little is scattered out of the beam.
    // Lee et al. (2005), with a 20 degree sun zenith and Petzold bb/b = 0.0183.
    const absorption = PURE_WATER_ABSORPTION[i] + columnFraction * (a[i] - PURE_WATER_ABSORPTION[i]);
    const backscatter = 0.0183 * b * columnFraction;
    kd[i] = 1.1 * absorption + 4.18 * (1 - 0.52 * Math.exp(-10.8 * absorption)) * backscatter;
  }
  return {c, b, a, kd};
}

function channels(value) {
  return Array.isArray(value) ? value.slice(0, 3) : [value, value, value];
}

// Adds participating-medium contributions (for example suspended sediment) to the water: each is
// {extinction, scattering} in 1/m, a number or an [r, g, b] array. Extinction adds to c; scattering (the part
// of it that turns into backscatter, coloured if per channel) adds to b; the rest is absorption, which also
// darkens daylight on its way down unless the item is `local: true` (a cloud near the camera, not a water
// column property). Returns {c, b, kd} with b per channel.
export function combineMedium(water, contributions = []) {
  const c = water.c.slice();
  const b = channels(water.b);
  const kd = water.kd.slice();
  for (const item of contributions) {
    if (!item) continue;
    const extinction = channels(item.extinction || 0);
    const scattering = channels(item.scattering ?? 0);
    for (let i = 0; i < 3; i++) {
      const scatter = Math.max(0, Math.min(extinction[i], scattering[i]));
      const absorb = Math.max(0, extinction[i] - scatter);
      c[i] += extinction[i] > 0 ? extinction[i] : 0;
      b[i] += scatter;
      // A local cloud (silt around the vehicle) does not shade the whole water column above it.
      if (!item.local) kd[i] += 1.1 * absorb + 0.15 * scatter;
    }
  }
  return {c, b, kd, a: water.a};
}

// Transmission of daylight from the surface down to `depth` metres, per channel.
export function daylightAt(depth, coefficients) {
  const z = Math.max(0, depth);
  return coefficients.kd.map(function channel(k) {
    return Math.exp(-k * z);
  });
}

// In-scattered daylight radiance seen along a ray of infinite length from `depth`, looking with vertical
// direction component `up` (+1 straight up, -1 straight down), relative to unit surface irradiance.
// Integral of b * E(z(s)) * exp(-c s) ds with E(z) = exp(-Kd z): b * E(depth) / (c - Kd * up).
export function waterRadianceAtInfinity(depth, up, coefficients) {
  const light = daylightAt(depth, coefficients);
  const b = channels(coefficients.b);
  return coefficients.c.map(function channel(c, i) {
    const k = Math.max(0.02, c - coefficients.kd[i] * up);
    return (1 + 0.85 * up) * b[i] * light[i] / k;
  });
}

// Rec. 709 luminance of a linear RGB triple.
export function luminance(rgb) {
  return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
}

// Exposure-lag smoothing: a first-order step in log space, `tau` seconds, so brightening and darkening are
// symmetric in stops. Returns the new exposure.
export function adaptExposure(current, target, seconds, tau) {
  if (!(current > 0)) return target;
  const step = 1 - Math.exp(-Math.max(0, seconds) / Math.max(1e-3, tau));
  return Math.exp(Math.log(current) + (Math.log(target) - Math.log(current)) * step);
}
