// Onboard camera look: what the vehicle's own camera adds to the picture, in the onboard view only.
// Effects: mild radial lens distortion, sensor noise that grows with the camera gain, and a light block
// (compression) look. It is a camera pass in the underwater optics pipeline (fx/pipeline.js setCameraPass):
// its input is the linear image after fx/exposure.js has applied the gain, before beautify and OutputPass, so it
// neither meters nor tone-maps. Auto-exposure belongs to fx/exposure.js alone.
// Noise is added in the exposed signal and scaled by the current gain (the 1x1 log-exposure texture), like read
// noise amplified by sensor gain: deep and lamps off is grainy, a bright lamp-lit scene is clean.
// Low / performance tiers (no pipeline) and the optics fallback (legacy look) have no camera look.
// Every coefficient here is a provisional presentation assumption: the research report has no quantified
// low-light noise, compression artefacts or X1 lens distortion (distortion is model specific; see
// docs/reference/real-rov-research.md). Photo eligibility is geometric and unaffected; camera transforms are
// never touched.
import * as THREE from 'three';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { registerFidelityItem } from '../fidelity.js';
import { exposureUniforms } from '../fx/exposure.js';
import { legacyWaterLook } from '../underwater_lighting.js';

export const CAMERA_LOOK_ITEM = 'cameraLook';
const STRENGTH = .6;
const NOISE_AT_REFERENCE = .004;   // linear noise amplitude at the reference gain
const REFERENCE_GAIN = 50;         // same reference as the partial AE compensation in fx/exposure.js
const MAX_GAIN_FACTOR = 8;

registerFidelityItem({
  id: CAMERA_LOOK_ITEM,
  labelKey: CAMERA_LOOK_ITEM,
  descriptionKey: 'cameraLookHelp',
  type: 'toggle',
  defaults: {real: true, assisted: false},
  exceedsReal: true,
  exceeds: function cleanerThanReal(value) {
    return value === false;
  },
}, {
  cameraLook: '機載鏡頭特性',
  cameraLookHelp: '機載畫面加入鏡頭畸變、隨增益變大的感光雜訊與輕度壓縮感（參數暫定）。低畫質檔不套用。',
});

const LOOK_SHADER = {
  uniforms: {
    tDiffuse: { value: null }, tCameraExposure: exposureUniforms.tCameraExposure,
    uBlocks: { value: new THREE.Vector2(800, 450) }, uAmount: { value: STRENGTH }, uTime: { value: 0 },
    uNoise: { value: NOISE_AT_REFERENCE }, uGain: { value: new THREE.Vector2(REFERENCE_GAIN, MAX_GAIN_FACTOR) },
  },
  vertexShader: `varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`,
  fragmentShader: `uniform sampler2D tDiffuse;
    uniform sampler2D tCameraExposure;
    uniform vec2 uBlocks;
    uniform float uAmount;
    uniform float uTime;
    uniform float uNoise;
    uniform vec2 uGain;
    varying vec2 vUv;
    float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
    void main() {
      vec2 p = vUv - .5;
      vec2 uv = clamp(.5 + p * (1. + uAmount * .08 * dot(p, p)), 0., 1.);
      vec2 block = (floor(uv * uBlocks) + .5) / uBlocks;
      vec4 c = texture2D(tDiffuse, uv);
      c.rgb = mix(c.rgb, texture2D(tDiffuse, block).rgb, uAmount * .18);
      float gain = exp(texelFetch(tCameraExposure, ivec2(0, 0), 0).r);
      float factor = clamp(gain / uGain.x, 0., uGain.y);
      float grain = hash(gl_FragCoord.xy + floor(uTime * 30.)) - .5;
      c.rgb = max(c.rgb + grain * uAmount * uNoise * factor, 0.);
      gl_FragColor = c;
    }`
};

export function installCameraLook({renderer, getMode, fidelity}) {
  const pass = new ShaderPass(LOOK_SHADER);
  pass.enabled = false;
  let attached = null;
  function wanted() {
    return getMode() === 'onboard' && fidelity.get(CAMERA_LOOK_ITEM) === true;
  }
  // Follows the pipeline: attaches when it exists (optics tiers), detaches when it is gone (low / disposed).
  function attach() {
    const pipeline = renderer.userData?.underwaterPipeline || null;
    if (pipeline === attached) return pipeline;
    if (attached && attached.cameraPass === pass) attached.setCameraPass(null);
    if (pipeline) pipeline.setCameraPass(pass);
    attached = pipeline;
    return pipeline;
  }
  // Called once per frame before the frame is rendered.
  function update() {
    const pipeline = attach();
    pass.enabled = !!pipeline && !legacyWaterLook(renderer) && wanted();
    if (!pass.enabled) return;
    const size = renderer.getDrawingBufferSize(new THREE.Vector2());
    pass.uniforms.uBlocks.value.set(Math.max(1, size.x / 2), Math.max(1, size.y / 2));
    pass.uniforms.uTime.value = performance.now() / 1000;
  }
  function active() {
    return pass.enabled;
  }
  return {update, active, pass};
}
