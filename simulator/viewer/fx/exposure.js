// Camera auto-exposure on the GPU: meter the linear scene image (centre-weighted log-average luminance),
// adapt towards the target with a lag like a real camera's exposure loop, and scale the image before the
// single tone-mapping step in OutputPass. No pixels are read back to the CPU.
// The target (fx/metering.js) protects highlights: a lamp-lit subject is not clipped just because dark water fills
// most of the frame. Convergence time, metering weights, the gain range and the highlight level are assumptions
// (the research report has no measured exposure behaviour for the vehicle camera); see fx/README.md.
// The same pass runs the camera's auto white balance (white_balance.js): only bright, near-neutral cells count
// as white-point candidates, so saturated water keeps its colour as in real footage, while lamp-lit near objects
// are balanced. It only rescales the red and blue that reached the sensor, within a limited range. The sensor's
// channel overlap (white_balance.js SENSOR_RESPONSE) is applied to the image before metering and gain.
import * as THREE from 'three';
import { Pass, FullScreenQuad } from 'three/addons/postprocessing/Pass.js';
import { WATER_COMMON, shareWaterUniforms } from './water_optics.js';
import { WHITE_BALANCE, WHITE_BALANCE_GLSL } from './white_balance.js';
import { METERING, meterTargetGlsl } from './metering.js';

export { WHITE_BALANCE };

export const EXPOSURE = Object.freeze({
  // Metering target: key, partial compensation around a reference gain, gain range and highlight protection
  // (fx/metering.js). The loop corrects only part of the metered error in stops, like a video camera with a
  // limited AE range, so brighter lamps still give a brighter picture; the highlight cap keeps a lamp-lit subject
  // from clipping when dark water fills most of the frame.
  ...METERING,
  tau: 0.35,          // seconds, first-order lag in stops
  maxStep: 0.25       // longest frame step the adaptation accepts, seconds
});
// The adapted log exposure (1x1 texture) for shaders that must not be exposed: unlit helpers and markers.
export const exposureUniforms = { tCameraExposure: { value: null }, tCameraBalance: { value: null } };
const neutralMaterials = new Map();
const EXPOSURE_GAIN = '(exp(-texelFetch(tCameraExposure, ivec2(0, 0), 0).r) / ' +
  'exp(texelFetch(tCameraBalance, ivec2(0, 0), 0).rgb))';
const NEUTRAL_VERTEX = `
  vec4 neutralLocal = vec4(transformed, 1.0);
  #ifdef USE_INSTANCING
  neutralLocal = instanceMatrix * neutralLocal;
  #endif
  vNeutralWorld = (modelMatrix * neutralLocal).xyz;
  #include <project_vertex>`;
// With fog, the helper fades along the same water path as everything else (towards the water colour of its
// own direction, not one flat fog colour); without fog it simply keeps its designed screen brightness.
const NEUTRAL_WATER = `
  #ifdef USE_FOG
  {
    vec3 neutralOrigin;
    vec3 neutralDir;
    float neutralLength = waterSegment(cameraPosition, vNeutralWorld, neutralOrigin, neutralDir);
    gl_FragColor.rgb = gl_FragColor.rgb * ${EXPOSURE_GAIN} * exp(-uWaterC * neutralLength) +
      waterInscatter(neutralOrigin, neutralDir, neutralLength) +
      lampInscatter(neutralOrigin, neutralDir, neutralLength);
  }
  #else
  gl_FragColor.rgb *= ${EXPOSURE_GAIN};
  #endif`;
const NEUTRAL_PLAIN = `
  gl_FragColor.rgb *= ${EXPOSURE_GAIN};
  #include <tonemapping_fragment>`;

function compileNeutralShader(shader) {
  shader.uniforms.tCameraExposure = exposureUniforms.tCameraExposure;
  shader.uniforms.tCameraBalance = exposureUniforms.tCameraBalance;
  const header = 'uniform sampler2D tCameraExposure;\nuniform sampler2D tCameraBalance;\n';
  const placed = shader.vertexShader.includes('#include <project_vertex>') &&
    shader.fragmentShader.includes('#include <fog_fragment>');
  if (!placed) {
    shader.fragmentShader = header + shader.fragmentShader.replace('#include <tonemapping_fragment>', NEUTRAL_PLAIN);
    return;
  }
  shareWaterUniforms(shader.uniforms);
  shader.vertexShader = 'varying vec3 vNeutralWorld;\n' +
    shader.vertexShader.replace('#include <project_vertex>', NEUTRAL_VERTEX);
  shader.fragmentShader = header + 'varying vec3 vNeutralWorld;\n' + WATER_COMMON +
    shader.fragmentShader.replace('#include <fog_fragment>', NEUTRAL_WATER);
}

// Unlit materials (training markers, lines, flow particles, lamp glows) keep their designed brightness on
// screen: they are divided by the camera exposure that the image is about to be multiplied with.
export function neutraliseExposure(material) {
  if (neutralMaterials.has(material)) return;
  const previous = material.onBeforeCompile;
  const key = material.customProgramCacheKey;
  neutralMaterials.set(material, { previous, key });
  material.onBeforeCompile = function compileNeutral(shader, renderer) {
    previous.call(this, shader, renderer);
    compileNeutralShader(shader);
  };
  const oldKey = key.bind(material);
  material.customProgramCacheKey = function neutralProgramKey() {
    return oldKey() + '|exposure-neutral-v4';
  };
  material.needsUpdate = true;
}

// Back to the materials' own shaders (legacy look or pipeline disposal).
export function restoreExposureNeutral() {
  for (const [material, original] of neutralMaterials) {
    material.onBeforeCompile = original.previous;
    material.customProgramCacheKey = original.key;
    material.needsUpdate = true;
  }
  neutralMaterials.clear();
}

const METER_WIDTH = 32;
const METER_HEIGHT = 18;

const VERTEX = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;

// Centre weighting of a meter cell (shared by the meter and the averaging passes).
const METER_WEIGHT = /* glsl */ `
  float meterWeight(vec2 uv) {
    return 1.0 - 0.7 * smoothstep(0.15, 0.75, length((uv - 0.5) * vec2(1.0, 0.8)) * 1.6);
  }
`;

// Each meter texel averages 4x4 bilinear taps of its footprint in log luminance, weighted towards the centre,
// and records its colour cast weighted as a white-point candidate (bright relative to the previous frame's
// average, close to neutral; white_balance.js).
const METER = /* glsl */ `
  uniform sampler2D tDiffuse;
  uniform sampler2D tHistory;
  uniform vec2 uCell;
  varying vec2 vUv;
  ${METER_WEIGHT}
  ${WHITE_BALANCE_GLSL}
  void main() {
    float sum = 0.0;
    vec3 colour = vec3(0.0);
    for (int y = 0; y < 4; y++) {
      for (int x = 0; x < 4; x++) {
        vec2 offset = (vec2(float(x), float(y)) - 1.5) * uCell * 0.25;
        vec3 c = sensorResponse(texture2D(tDiffuse, vUv + offset).rgb);
        sum += log(max(dot(c, vec3(0.2126, 0.7152, 0.0722)), 1e-5));
        colour += c;
      }
    }
    float weight = meterWeight(vUv);
    // Colour cast of this cell: log(red / green) and log(blue / green) of the summed light.
    vec2 colourCast = log(max(colour.rb, vec2(1e-6)) / max(colour.g, 1e-6));
    float luminance = max(dot(colour / 16.0, vec3(0.2126, 0.7152, 0.0722)), 1e-6);
    float average = exp(texelFetch(tHistory, ivec2(0, 0), 0).b);
    float candidate = weight * brightnessWeight(luminance, average) * whitePointWeight(colourCast);
    gl_FragColor = vec4(sum / 16.0 * weight, candidate, colourCast.x * candidate, colourCast.y * candidate);
  }`;

// One texel: log exposure, moved towards the metered target by the elapsed time; also the metered log average and
// the log of the bright end (fx/metering.js) for diagnostics.
const ADAPT = /* glsl */ `
  uniform sampler2D tMeter;
  uniform sampler2D tPrevious;
  uniform float uStep;
  uniform float uReset;
  varying vec2 vUv;
  ${METER_WEIGHT}
  ${meterTargetGlsl(METER_WIDTH, METER_HEIGHT)}
  void main() {
    vec3 metered = meterTarget(tMeter);
    float previous = texelFetch(tPrevious, ivec2(0, 0), 0).r;
    float next = uReset > 0.5 ? metered.x : previous + (metered.x - previous) * uStep;
    gl_FragColor = vec4(next, metered.x, metered.y, metered.z);
  }`;

// One texel: log channel gains (red, green, blue) of the white balance, lagged like the exposure.
const BALANCE = /* glsl */ `
  uniform sampler2D tMeter;
  uniform sampler2D tPrevious;
  uniform float uStep;
  uniform float uReset;
  uniform float uBalanceScale;
  varying vec2 vUv;
  ${METER_WEIGHT}
  ${WHITE_BALANCE_GLSL}
  void main() {
    vec2 colourCast = vec2(0.0);
    float candidates = 0.0;
    float weights = 0.0;
    for (int y = 0; y < ${METER_HEIGHT}; y++) {
      for (int x = 0; x < ${METER_WIDTH}; x++) {
        vec4 m = texelFetch(tMeter, ivec2(x, y), 0);
        colourCast += m.ba;
        candidates += m.g;
        weights += meterWeight((vec2(float(x), float(y)) + 0.5) / vec2(${METER_WIDTH}.0, ${METER_HEIGHT}.0));
      }
    }
    vec3 target = uBalanceScale *
      whiteBalanceLogGains(colourCast / max(candidates, 1e-6), candidates / max(weights, 1e-4));
    vec3 previous = texelFetch(tPrevious, ivec2(0, 0), 0).rgb;
    vec3 next = uReset > 0.5 ? target : previous + (target - previous) * uStep;
    gl_FragColor = vec4(next, 1.0);
  }`;

const APPLY = /* glsl */ `
  uniform sampler2D tDiffuse;
  uniform sampler2D tExposure;
  uniform sampler2D tBalance;
  varying vec2 vUv;
  ${WHITE_BALANCE_GLSL}
  void main() {
    vec4 c = texture2D(tDiffuse, vUv);
    c.rgb = sensorResponse(c.rgb);
    vec3 gain = exp(texelFetch(tExposure, ivec2(0, 0), 0).r + texelFetch(tBalance, ivec2(0, 0), 0).rgb);
    gl_FragColor = vec4(c.rgb * gain, c.a);
  }`;

function target(width, height, type = THREE.HalfFloatType) {
  return new THREE.WebGLRenderTarget(width, height, {
    type, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter,
    depthBuffer: false
  });
}

export class AutoExposurePass extends Pass {
  constructor() {
    super();
    this.meter = target(METER_WIDTH, METER_HEIGHT);
    this.history = [target(1, 1, THREE.FloatType), target(1, 1, THREE.FloatType)];
    this.balanceHistory = [target(1, 1, THREE.FloatType), target(1, 1, THREE.FloatType)];
    this.current = 0;
    this.reset = true;
    this.lastTime = null;
    this.meterMaterial = new THREE.ShaderMaterial({
      uniforms: {
        tDiffuse: { value: null }, tHistory: { value: null },
        uCell: { value: new THREE.Vector2(1 / METER_WIDTH, 1 / METER_HEIGHT) }
      },
      vertexShader: VERTEX, fragmentShader: METER, depthTest: false, depthWrite: false
    });
    this.adaptMaterial = new THREE.ShaderMaterial({
      uniforms: {
        tMeter: { value: this.meter.texture }, tPrevious: { value: null }, uStep: { value: 1 },
        uReset: { value: 1 }, uRange: { value: new THREE.Vector3(EXPOSURE.key, EXPOSURE.minimum, EXPOSURE.maximum) },
        uPartial: { value: new THREE.Vector2(EXPOSURE.compensation, Math.log(EXPOSURE.reference)) },
        uHighlight: { value: EXPOSURE.highlight }
      },
      vertexShader: VERTEX, fragmentShader: ADAPT, depthTest: false, depthWrite: false
    });
    this.balanceMaterial = new THREE.ShaderMaterial({
      uniforms: {
        tMeter: { value: this.meter.texture }, tPrevious: { value: null }, uStep: { value: 1 },
        uReset: { value: 1 }, uBalanceScale: { value: 1 }
      },
      vertexShader: VERTEX, fragmentShader: BALANCE, depthTest: false, depthWrite: false
    });
    this.applyMaterial = new THREE.ShaderMaterial({
      uniforms: { tDiffuse: { value: null }, tExposure: { value: null }, tBalance: { value: null } },
      vertexShader: VERTEX, fragmentShader: APPLY, depthTest: false, depthWrite: false
    });
    this.quad = new FullScreenQuad(null);
    // When the pipeline's last pass applies the gain itself (fx/camera_output.js), this pass only meters and adapts
    // (three tiny passes) and hands the scene image on unchanged instead of copying it at full size.
    this.deferApply = false;
    // Optional override while the camera is above water ({compensation, reference, balance, highlight?},
    // fx/daylight.js); null keeps the underwater camera model above.
    this.metering = null;
  }

  applyMetering() {
    const metering = this.metering;
    const compensation = metering ? metering.compensation : EXPOSURE.compensation;
    const reference = metering ? metering.reference : EXPOSURE.reference;
    this.adaptMaterial.uniforms.uPartial.value.set(compensation, Math.log(reference));
    // The daylight camera above water keeps its fixed gain unless its override names a highlight level.
    this.adaptMaterial.uniforms.uHighlight.value = metering ? metering.highlight ?? 0 : EXPOSURE.highlight;
    // The override's `balance` is the share of the camera's own white balance to apply (0 = fixed daylight).
    this.balanceMaterial.uniforms.uBalanceScale.value = metering ? metering.balance : 1;
  }

  // Seconds since the previous metered frame, from the wall clock; capped so a stall does not jump.
  frameStep() {
    const now = performance.now() / 1000;
    const seconds = this.lastTime === null ? 0 : Math.min(EXPOSURE.maxStep, Math.max(0, now - this.lastTime));
    this.lastTime = now;
    return 1 - Math.exp(-seconds / EXPOSURE.tau);
  }

  render(renderer, writeBuffer, readBuffer) {
    this.applyMetering();
    this.meterMaterial.uniforms.tDiffuse.value = readBuffer.texture;
    this.meterMaterial.uniforms.tHistory.value = this.history[this.current].texture;
    this.quad.material = this.meterMaterial;
    renderer.setRenderTarget(this.meter);
    this.quad.render(renderer);
    const previous = this.history[this.current];
    const next = this.history[1 - this.current];
    this.adaptMaterial.uniforms.tPrevious.value = previous.texture;
    const step = this.frameStep();
    this.adaptMaterial.uniforms.uStep.value = step;
    this.adaptMaterial.uniforms.uReset.value = this.reset ? 1 : 0;
    this.quad.material = this.adaptMaterial;
    renderer.setRenderTarget(next);
    this.quad.render(renderer);
    const balancePrevious = this.balanceHistory[this.current];
    const balanceNext = this.balanceHistory[1 - this.current];
    this.balanceMaterial.uniforms.tPrevious.value = balancePrevious.texture;
    this.balanceMaterial.uniforms.uStep.value = step;
    this.balanceMaterial.uniforms.uReset.value = this.reset ? 1 : 0;
    this.quad.material = this.balanceMaterial;
    renderer.setRenderTarget(balanceNext);
    this.quad.render(renderer);
    this.current = 1 - this.current;
    this.reset = false;
    exposureUniforms.tCameraExposure.value = next.texture;
    exposureUniforms.tCameraBalance.value = balanceNext.texture;
    this.needsSwap = !this.deferApply;
    if (this.deferApply) return;
    this.applyMaterial.uniforms.tDiffuse.value = readBuffer.texture;
    this.applyMaterial.uniforms.tExposure.value = next.texture;
    this.applyMaterial.uniforms.tBalance.value = balanceNext.texture;
    this.quad.material = this.applyMaterial;
    renderer.setRenderTarget(this.renderToScreen ? null : writeBuffer);
    if (this.clear) renderer.clear();
    this.quad.render(renderer);
  }

  // Diagnostics for tools only (synchronous GPU read): current exposure, target and metered log luminance.
  read(renderer) {
    const pixel = new Float32Array(4);
    renderer.readRenderTargetPixels(this.history[this.current], 0, 0, 1, 1, pixel);
    const value = Array.from(pixel);
    const balance = new Float32Array(4);
    renderer.readRenderTargetPixels(this.balanceHistory[this.current], 0, 0, 1, 1, balance);
    return { exposure: Math.exp(value[0]), target: Math.exp(value[1]), meteredLuminance: Math.exp(value[2]),
      brightLuminance: Math.exp(value[3]), whiteBalance: [Math.exp(balance[0]), 1, Math.exp(balance[2])] };
  }

  dispose() {
    this.meter.dispose();
    this.history.concat(this.balanceHistory).forEach(function disposeTarget(item) {
      item.dispose();
    });
    this.balanceMaterial.dispose();
    this.meterMaterial.dispose();
    this.adaptMaterial.dispose();
    this.applyMaterial.dispose();
    this.quad.dispose();
  }
}
