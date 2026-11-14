// Onboard camera look: what the vehicle's own camera adds to the picture, applied only in the onboard view.
// Effects: mild radial lens distortion, low-light sensor noise, a light compression (block) look and slow
// auto-exposure. Water optics (attenuation, backscatter, fog) are not done here; they belong to the scene.
// The scene is rendered exactly as without this module, copied from the canvas and re-drawn through one shader,
// so tone mapping and colour space are untouched; the effects work on display-encoded values.
// Every coefficient, response time and lens parameter is a provisional presentation assumption, not a measured
// camera or vehicle specification (docs/reference/real-rov-research.md has no calibrated values for these).
// The `cameraLook` fidelity item turns it on in `real` (a real feed has these artefacts) and off in `assisted`.
// TODO(fx pipeline): main has no fx pipeline yet. When simulator/viewer/fx/ lands with a `setCameraPass` hook,
// register `cameraPass` below through it and delete render(); the shader and exposure logic carry over unchanged.
// Geometry, camera transforms and observation evidence are never modified; photo capture keeps the clean frame.
import * as THREE from 'three';
import {registerFidelityItem} from '../fidelity.js';

export const CAMERA_LOOK_ITEM = 'cameraLook';
const EXPOSURE_TIME_MS = 900;
const METER_INTERVAL_MS = 200;
const EXPOSURE_TARGET = .45;   // display-encoded mid tone the meter steers the centre toward
const EXPOSURE_LIMITS = [.8, 1.3];
const STRENGTH = .6;

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
  cameraLookHelp: '機載畫面加入鏡頭畸變、低光雜訊、輕度壓縮與自動曝光遲滯（參數暫定）。關閉時為乾淨畫面。',
});

const VERTEX = 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }';
const FRAGMENT = `
  varying vec2 vUv;
  uniform sampler2D image;
  uniform vec2 blocks;
  uniform float amount;
  uniform float time;
  uniform float exposure;
  float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
  void main() {
    vec2 p = vUv - .5;
    vec2 uv = clamp(.5 + p * (1. + amount * .08 * dot(p, p)), 0., 1.);
    vec2 block = (floor(uv * blocks) + .5) / blocks;
    vec3 color = mix(texture2D(image, uv).rgb, texture2D(image, block).rgb, amount * .18) * exposure;
    float luminance = dot(color, vec3(.2126, .7152, .0722));
    float grain = hash(gl_FragCoord.xy + floor(time * 30.)) - .5;
    color += grain * amount * .06 * (1. - smoothstep(.1, .5, luminance));
    gl_FragColor = vec4(clamp(color, 0., 1.), 1.);
  }`;

export function installCameraLook({renderer, scene, camera, getMode, fidelity}) {
  const uniforms = {
    image: {value: null}, blocks: {value: new THREE.Vector2(800, 450)}, amount: {value: STRENGTH},
    time: {value: 0}, exposure: {value: 1},
  };
  const material = new THREE.ShaderMaterial({uniforms, vertexShader: VERTEX, fragmentShader: FRAGMENT});
  material.toneMapped = false;
  const screen = new THREE.Scene();
  screen.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material));
  const screenCamera = new THREE.Camera();
  const size = new THREE.Vector2();
  const origin = new THREE.Vector2();
  const pixel = new Uint8Array(4);
  let frame = null;
  let metered = 1;
  let meteredAt = -Infinity;
  let lastTime = performance.now();
  function active() {
    return getMode() === 'onboard' && fidelity.get(CAMERA_LOOK_ITEM) === true;
  }
  function ensureFrame() {
    renderer.getDrawingBufferSize(size);
    if (frame && frame.image.width === size.x && frame.image.height === size.y) return;
    frame?.dispose();
    frame = new THREE.FramebufferTexture(size.x, size.y);
    uniforms.image.value = frame;
    uniforms.blocks.value.set(Math.max(1, size.x / 2), Math.max(1, size.y / 2));
  }
  // Centre-weighted meter on the plain frame, sampled a few times a second; exposure follows with a lag.
  function meter(now) {
    if (now - meteredAt < METER_INTERVAL_MS) return;
    meteredAt = now;
    const gl = renderer.getContext();
    gl.readPixels(Math.floor(size.x / 2), Math.floor(size.y / 2), 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    const luminance = (pixel[0] * .2126 + pixel[1] * .7152 + pixel[2] * .0722) / 255;
    metered = THREE.MathUtils.clamp(EXPOSURE_TARGET / Math.max(.05, luminance), ...EXPOSURE_LIMITS);
  }
  function cameraPass(now) {
    ensureFrame();
    renderer.render(scene, camera);
    meter(now);
    renderer.copyFramebufferToTexture(origin, frame);
    const exposure = uniforms.exposure;
    exposure.value += (metered - exposure.value) * (1 - Math.exp(-(now - lastTime) / EXPOSURE_TIME_MS));
    uniforms.time.value = now / 1000;
    renderer.render(screen, screenCamera);
  }
  // Draws one frame to the canvas: the plain scene, or the scene through the camera look in the onboard view.
  function render() {
    const now = performance.now();
    if (active()) cameraPass(now);
    else {
      uniforms.exposure.value = 1;
      renderer.render(scene, camera);
    }
    lastTime = now;
  }
  return {render, active};
}
