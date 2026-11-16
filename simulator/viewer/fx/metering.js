// Camera auto-exposure target from the meter grid: centre-weighted log-average metering with partial
// compensation (as before), plus highlight protection. Pure module without imports: exposure.js builds its GPU
// adaptation pass from these constants and the GLSL below, and node tests run the same rule on the CPU
// (meterTarget).
//
// Why highlight protection: a log-average meter is dominated by whatever covers most of the frame. Under the
// vehicle lamps that is dark water, so the meter opens the camera up and the lamp-lit subject in the middle
// (a fish, a hull, the seabed at 1 m) clips to white. Video cameras do not do that: their AE also watches the
// bright end of the histogram and gives up gain when a sizeable bright area would saturate (highlight priority).
// Here the bright end is the level that the brightest `highlightShare` of the centre-weighted frame exceeds (a
// histogram of the meter cells in quarter stops); the gain is capped so that this level lands at `highlight` on
// the exposed scale (before the ACES curve). Anything smaller (a specular glint, one bright cell) may still clip,
// as in footage. The cap is a hard minimum with the ordinary target, so frames without a bright area (lamps off,
// uniform water) are untouched until the bright end reaches it.
// All numbers are assumptions (no measured AE behaviour of the vehicle camera exists); see fx/README.md.
export const METERING = Object.freeze({
  key: 0.15,            // mid-grey the meter aims for, before ACES
  compensation: 0.65,   // share of the metered error in stops the loop corrects, around the reference gain
  reference: 50.0,
  minimum: 0.3,         // strongest darkening (bright shallow water, sun-lit sand)
  maximum: 400.0,       // most gain the camera adds in the dark
  highlight: 0.8,       // exposed level (linear, before ACES; about sRGB 220) the bright end may reach; 0 = off
  highlightShare: 0.05  // share of the centre-weighted frame that counts as "the bright end"
});

// Histogram of the cells around the log average: quarter stops from 2 stops below to 10 stops above.
const BIN_STEP = Math.LN2 / 4;
const BIN_BELOW = 8;
const BINS = 48;

function binOf(cellLog, average) {
  const index = Math.floor((cellLog - average) / BIN_STEP + 0.5) + BIN_BELOW;
  return Math.min(Math.max(index, 0), BINS - 1);
}

// Log luminance that the brightest `share` of the weight exceeds, from the histogram (linear inside a bin).
function brightLevel(bins, weights, average, share) {
  const needed = share * weights;
  let above = 0;
  for (let i = BINS - 1; i >= 0; i--) {
    if (bins[i] > 0 && above + bins[i] >= needed) {
      const part = (needed - above) / bins[i];
      return average + (i - BIN_BELOW - 0.5 + 1 - part) * BIN_STEP;
    }
    above += bins[i];
  }
  return average - (BIN_BELOW + 0.5) * BIN_STEP;
}

/**
 * Log exposure target for meter cells [{log, weight}] (log luminance of the cell, centre weight). `options` may
 * override compensation, reference and highlight (the above-water daylight camera, fx/daylight.js). Returns
 * {average, bright, target}: centre-weighted log average, log level of the bright end, target log gain.
 */
export function meterTarget(cells, options = {}) {
  const compensation = options.compensation ?? METERING.compensation;
  const reference = options.reference ?? METERING.reference;
  const highlight = options.highlight ?? METERING.highlight;
  let logSum = 0;
  let weights = 0;
  for (const cell of cells) {
    logSum += cell.log * cell.weight;
    weights += cell.weight;
  }
  const average = logSum / Math.max(weights, 1e-4);
  const bins = new Array(BINS).fill(0);
  for (const cell of cells) bins[binOf(cell.log, average)] += cell.weight;
  const bright = brightLevel(bins, weights, average, METERING.highlightShare);
  const full = Math.log(METERING.key) - average;
  let target = compensation * full + (1 - compensation) * Math.log(reference);
  if (highlight > 0) target = Math.min(target, Math.log(highlight) - bright);
  target = Math.min(Math.max(target, Math.log(METERING.minimum)), Math.log(METERING.maximum));
  return {average, bright, target};
}

// GLSL of the same rule for the adaptation pass. Expects METER_WEIGHT's meterWeight() and the meter texture holding
// weight * log luminance in .r; declares its uniforms. Returns vec3(target, average, bright).
export function meterTargetGlsl(width, height) {
  const step = BIN_STEP.toFixed(6);
  return /* glsl */ `
  uniform vec3 uRange;
  uniform vec2 uPartial;
  uniform float uHighlight;
  float meterCellWeight(int x, int y) {
    return meterWeight((vec2(float(x), float(y)) + 0.5) / vec2(${width}.0, ${height}.0));
  }
  vec3 meterTarget(sampler2D meter) {
    float logSum = 0.0;
    float weights = 0.0;
    for (int y = 0; y < ${height}; y++) {
      for (int x = 0; x < ${width}; x++) {
        logSum += texelFetch(meter, ivec2(x, y), 0).r;
        weights += meterCellWeight(x, y);
      }
    }
    float average = logSum / max(weights, 1e-4);
    float bins[${BINS}];
    for (int i = 0; i < ${BINS}; i++) bins[i] = 0.0;
    for (int y = 0; y < ${height}; y++) {
      for (int x = 0; x < ${width}; x++) {
        float weight = meterCellWeight(x, y);
        float cellLog = texelFetch(meter, ivec2(x, y), 0).r / max(weight, 1e-4);
        int index = int(floor((cellLog - average) / ${step} + 0.5)) + ${BIN_BELOW};
        bins[clamp(index, 0, ${BINS - 1})] += weight;
      }
    }
    float needed = ${METERING.highlightShare.toFixed(3)} * weights;
    float above = 0.0;
    float bright = average - ${(BIN_BELOW + 0.5).toFixed(1)} * ${step};
    for (int i = ${BINS - 1}; i >= 0; i--) {
      if (bins[i] > 0.0 && above + bins[i] >= needed) {
        float part = (needed - above) / bins[i];
        bright = average + (float(i - ${BIN_BELOW}) + 0.5 - part) * ${step};
        break;
      }
      above += bins[i];
    }
    float full = log(uRange.x) - average;
    float target = uPartial.x * full + (1.0 - uPartial.x) * uPartial.y;
    if (uHighlight > 0.0) target = min(target, log(uHighlight) - bright);
    target = clamp(target, log(uRange.y), log(uRange.z));
    return vec3(target, average, bright);
  }
`;
}
