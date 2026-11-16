// Camera auto white balance model: which parts of the frame the camera trusts as "white", and how far it may
// correct. Pure module without imports: exposure.js builds its GPU meter from these constants and the GLSL
// below, and node tests run the same rules on the CPU (whiteBalanceGains).
//
// Why it works this way (docs/design/underwater-look/README.md has the footage and numbers):
// - Working-camera footage with auto white balance keeps the water strongly coloured: net pens at R/G 0-0.1 and
//   B/G 0.25-0.7 (linear), open reef water deep blue, lake and harbour water green. A camera's AWB only accepts
//   pixels close to the illuminant locus as white-point candidates; saturated water is rejected, so the camera
//   keeps its default (daylight) balance instead of pulling the water to grey.
// - Near, lamp-lit objects are close to neutral (white LED light over a short path) and do become candidates, so
//   under the lamps the camera balances on them, as footage of lit nets, fish and hulls shows.
// - Dark cells carry noise, not colour information: each cell counts in proportion to how bright it is relative
//   to the frame (the previous frame's metered average).
// - Correction runs along the colour-temperature axis (warm / cool, red against blue) with a limited range and
//   only a small green-magenta tint correction, like a camera's AWB range; the old grey-world balance corrected
//   the green cast fully along the tint axis, which turned green and grey-green water mauve and grey.
// All numbers are assumptions (no measured AWB behaviour of the vehicle camera exists), tuned on the footage
// colour targets.
export const WHITE_BALANCE = Object.freeze({
  strength: 0.8,        // share of the candidates' cast removed (log ratios)
  tintGate: 0.25,       // width of the candidate gate across the green-magenta axis (log units)
  temperatureGate: 0.9, // width of the candidate gate along the warm-cool axis (log units)
  confidenceLow: 0.03,  // share of the (centre-weighted) frame that must be candidates before the camera acts
  confidenceHigh: 0.25, // share at which it corrects fully
  temperatureLimit: 0.6, // largest warm / cool correction, log gain per channel (about 1.8x)
  tintLimit: 0.08       // largest green-magenta correction, log gain (about 1.08x)
});

// Sensor spectral overlap: each colour channel of a real camera also sees part of its neighbours' light (broad
// Bayer dye filters). The renderer carries three narrow bands (620 / 540 / 470 nm); a real red filter also passes
// 570-600 nm light, which water absorbs far less than 620 nm, so deep green and cyan water still records some red.
// Rows: sensor R, G, B from the rendered R, G, B. The shares are assumptions, set so open water of each type stays
// inside the footage ranges (R/G 0.1-0.5 in green, harbour and reef water instead of zero; README of
// docs/design/underwater-look/).
export const SENSOR_RESPONSE = Object.freeze([
  [0.8, 0.2, 0.0],
  [0.06, 0.88, 0.06],
  [0.0, 0.15, 0.85],
]);

/** The rendered linear colour as the camera's sensor records it (before exposure and white balance). */
export function sensorResponse(rgb) {
  return SENSOR_RESPONSE.map((row) => row[0] * rgb[0] + row[1] * rgb[1] + row[2] * rgb[2]);
}

function smoothstep(low, high, value) {
  const k = Math.max(0, Math.min(1, (value - low) / (high - low)));
  return k * k * (3 - 2 * k);
}

function clampAbs(value, limit) {
  return Math.max(-limit, Math.min(limit, value));
}

/** Candidate weight of a cell with log(R/G) = castR and log(B/G) = castB: 1 near neutral, 0 for saturated water. */
export function whitePointWeight(castR, castB) {
  const temperature = (castR - castB) / 2 / WHITE_BALANCE.temperatureGate;
  const tint = (castR + castB) / 2 / WHITE_BALANCE.tintGate;
  return Math.exp(-tint * tint - temperature * temperature);
}

/**
 * Target channel gains [r, 1, b] for rendered cells [{rgb: [r, g, b] linear, weight: centre weight}], seen through
 * the sensor response. Mirrors the GPU meter and balance passes of exposure.js (without the time lag).
 */
export function whiteBalanceGains(rendered) {
  const cells = rendered.map((cell) => ({rgb: sensorResponse(cell.rgb), weight: cell.weight}));
  const luminances = cells.map((cell) => 0.2126 * cell.rgb[0] + 0.7152 * cell.rgb[1] + 0.0722 * cell.rgb[2]);
  const weights = cells.map((cell) => cell.weight ?? 1);
  const total = weights.reduce((sum, w) => sum + w, 0);
  const average = Math.exp(luminances.reduce((sum, l, i) => sum + Math.log(Math.max(l, 1e-5)) * weights[i], 0) /
    Math.max(total, 1e-6));
  let candidates = 0;
  let castR = 0;
  let castB = 0;
  cells.forEach(function meterCell(cell, i) {
    const green = Math.max(cell.rgb[1], 1e-6);
    const r = Math.log(Math.max(cell.rgb[0], 1e-6) / green);
    const b = Math.log(Math.max(cell.rgb[2], 1e-6) / green);
    const w = weights[i] * luminances[i] / (luminances[i] + average) * whitePointWeight(r, b);
    candidates += w;
    castR += r * w;
    castB += b * w;
  });
  return gainsFromCast(castR / Math.max(candidates, 1e-6), castB / Math.max(candidates, 1e-6),
    candidates / Math.max(total, 1e-6)).map(Math.exp);
}

/** Log gains [r, 0, b] for an average candidate cast and the candidate share of the frame. */
export function gainsFromCast(castR, castB, share) {
  const confidence = smoothstep(WHITE_BALANCE.confidenceLow, WHITE_BALANCE.confidenceHigh, share);
  const temperature = clampAbs(-WHITE_BALANCE.strength * (castR - castB) / 2, WHITE_BALANCE.temperatureLimit);
  const tint = clampAbs(-WHITE_BALANCE.strength * (castR + castB) / 2, WHITE_BALANCE.tintLimit);
  return [(temperature + tint) * confidence, 0, (-temperature + tint) * confidence];
}

function glslFloat(value) {
  return Number(value).toFixed(5);
}

const SENSOR_COLUMNS = [0, 1, 2].map(function sensorColumn(j) {
  return SENSOR_RESPONSE.map((row) => glslFloat(row[j])).join(', ');
});

// GLSL used by exposure.js: the candidate weight of a cell and the gains from the averaged cast.
export const WHITE_BALANCE_GLSL = `
  // GLSL mat3 takes columns: column j holds what rendered channel j adds to each sensor channel.
  const mat3 SENSOR_RESPONSE = mat3(
    ${SENSOR_COLUMNS[0]},
    ${SENSOR_COLUMNS[1]},
    ${SENSOR_COLUMNS[2]});
  vec3 sensorResponse(vec3 c) {
    return SENSOR_RESPONSE * c;
  }
  float whitePointWeight(vec2 colourCast) {
    float temperature = (colourCast.x - colourCast.y) * 0.5 / ${glslFloat(WHITE_BALANCE.temperatureGate)};
    float tint = (colourCast.x + colourCast.y) * 0.5 / ${glslFloat(WHITE_BALANCE.tintGate)};
    return exp(-tint * tint - temperature * temperature);
  }
  vec3 whiteBalanceLogGains(vec2 colourCast, float share) {
    float confidence = smoothstep(${glslFloat(WHITE_BALANCE.confidenceLow)}, ${glslFloat(WHITE_BALANCE.confidenceHigh)},
      share);
    float temperature = clamp(-${glslFloat(WHITE_BALANCE.strength)} * (colourCast.x - colourCast.y) * 0.5,
      -${glslFloat(WHITE_BALANCE.temperatureLimit)}, ${glslFloat(WHITE_BALANCE.temperatureLimit)});
    float tint = clamp(-${glslFloat(WHITE_BALANCE.strength)} * (colourCast.x + colourCast.y) * 0.5,
      -${glslFloat(WHITE_BALANCE.tintLimit)}, ${glslFloat(WHITE_BALANCE.tintLimit)});
    return vec3(temperature + tint, 0.0, tint - temperature) * confidence;
  }
`;
