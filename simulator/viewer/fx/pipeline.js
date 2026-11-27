// Screen pipeline for the optics tiers: scene (linear HDR) -> camera auto-exposure -> optional camera pass
// (T14b) -> beautify finish -> OutputPass, the only tone-mapping and output-transfer step -> daylight grade
// (above water only, fx/daylight.js).
// The exposure gain, a foldable camera pass (the onboard camera look), the beautify vignette and the output step
// run as one full-screen pass (fx/camera_output.js); the exposure pass itself then only meters. A camera pass that
// cannot be folded still runs on its own between them, on the exposed image, as before.
// The renderer's screen render is wrapped once, so normal frames, render_movie.js, recordings and photo
// captures all take the same path. Offscreen renders and the low / fallback tiers bypass it untouched.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { updateReflections, disposeReflections } from './reflections.js';
import { updateWaterSurface, disposeWaterSurface } from './surface.js';
import { updateSuspension, hideSuspension } from './suspension.js';
import { updateWaterOptics, createWaterBackground, horizontalWaterColour, hideLegacyBeams } from './water_optics.js';
import { AutoExposurePass } from './exposure.js';
import { DAYLIGHT_GRADE } from './daylight.js';
import { CameraOutputPass, CAMERA_LOOK_FOLD } from './camera_output.js';
import { beautifyEnabled, BEAUTIFY_ID } from './beautify.js';
import { getFidelity } from '../fidelity.js';
import { legacyWaterLook } from '../underwater_lighting.js';
import { renderQualityState } from '../render_quality.js';

const pipelines = new WeakMap();
const drawingSize = new THREE.Vector2();

function isLowMode(renderer) {
  return ['performance', 'low'].includes(renderQualityState(renderer)?.mode);
}

function buildComposer(state, renderer, scene, camera) {
  state.composer = new EffectComposer(renderer);
  state.renderPass = new RenderPass(scene, camera);
  state.exposurePass = new AutoExposurePass();
  state.outputPass = new CameraOutputPass();
  state.composer.addPass(state.renderPass);
  state.composer.addPass(state.exposurePass);
  if (state.cameraPass) state.composer.addPass(state.cameraPass);
  state.composer.addPass(state.outputPass);
  // Daylight camera colour rendering, after tone mapping; only enabled while the camera is above water.
  state.gradePass = new ShaderPass(DAYLIGHT_GRADE);
  state.gradePass.enabled = false;
  state.composer.addPass(state.gradePass);
}

function resizeComposer(state, renderer) {
  const size = renderer.getDrawingBufferSize(drawingSize);
  if (size.x === state.width && size.y === state.height) return;
  state.composer.setPixelRatio(1);
  state.composer.setSize(size.x, size.y);
  state.width = size.x;
  state.height = size.y;
}

// Leaves the optics look: hides the water-only objects and lets the next optics frame re-meter at once.
function leaveOptics(state, scene, camera, renderer) {
  state.background.visible = false;
  updateWaterSurface(state.surface, camera, scene, true);
  hideSuspension(scene);
  updateReflections(scene, renderQualityState(renderer)?.mode, true);
  if (state.exposurePass) state.exposurePass.reset = true;
}

function renderOptics(state, original, scene, camera) {
  const renderer = state.renderer;
  const beauty = beautifyEnabled();
  if (state.background.parent !== scene) scene.add(state.background);
  state.background.visible = camera.position.y < 0;
  state.scenes.add(scene);
  const { water } = updateWaterOptics(scene, { beauty, camera });
  const fog = scene.fog?.color;
  if (fog) {
    state.fogColour.copy(fog);
    horizontalWaterColour(Math.max(0, -camera.position.y), water, fog);
    if (scene.userData.weatherLight) fog.multiply(scene.userData.weatherLight);
  }
  updateReflections(scene, renderQualityState(renderer)?.mode);
  updateWaterSurface(state.surface, camera, scene, false, beauty);
  updateSuspension(scene, camera, renderQualityState(renderer));
  if (!state.composer) buildComposer(state, renderer, scene, camera);
  // Above water the daylight camera model (fx/daylight.js) replaces the underwater metering.
  state.exposurePass.metering = camera.position.y > 0 ? scene.userData.daylightMetering ?? null : null;
  state.gradePass.enabled = !!state.exposurePass.metering;
  resizeComposer(state, renderer);
  state.renderPass.scene = scene;
  state.renderPass.camera = camera;
  const look = state.cameraPass;
  const folded = !!look?.enabled && look.outputFold === CAMERA_LOOK_FOLD;
  const separate = !!look?.enabled && !folded;
  state.exposurePass.deferApply = !separate;
  state.outputPass.configure({ applyExposure: !separate, look: folded ? look.uniforms : null,
    vignette: beauty ? 1 : 0 });
  const exposure = renderer.toneMappingExposure;
  renderer.toneMappingExposure = 1;
  const restoreBeams = hideLegacyBeams(scene);
  state.busy = true;
  // A folded camera pass keeps its place in the pass list but is drawn by the output pass this frame.
  if (folded) look.enabled = false;
  try {
    state.composer.render();
  } finally {
    if (folded) look.enabled = true;
    state.busy = false;
    restoreBeams();
    renderer.toneMappingExposure = exposure;
    if (fog) fog.copy(state.fogColour);
  }
}

export { addMediumContributor } from './water_optics.js';

export function installUnderwaterPipeline(renderer, { surface = null } = {}) {
  if (pipelines.has(renderer)) return pipelines.get(renderer);
  if (isLowMode(renderer)) return null;
  const original = renderer.render.bind(renderer);
  const state = {
    renderer, surface, scenes: new Set(), composer: null, busy: false, cameraPass: null, width: 0, height: 0,
    background: createWaterBackground(), optics: false, fogColour: new THREE.Color(),
    get enhancements() {
      return beautifyEnabled();
    },
    // Kept for callers of the first pipeline revision; the fidelity item is the single source of truth.
    setEnhancements: function setEnhancements(enabled) {
      getFidelity().set(BEAUTIFY_ID, !!enabled);
    },
    setCameraPass: function setCameraPass(pass) {
      if (this.cameraPass && this.composer) this.composer.removePass(this.cameraPass);
      this.cameraPass = pass;
      if (pass && this.composer) this.composer.insertPass(pass, 2);
    },
    exposure: function exposure() {
      return this.exposurePass ? this.exposurePass.read(renderer) : null;
    },
    dispose: function dispose() {
      this.composer?.passes.filter(pass => pass !== this.cameraPass)
        .forEach(function disposePass(pass) {
          pass.dispose?.();
        });
      this.composer?.dispose();
      disposeWaterSurface(surface);
      this.scenes.forEach(function disposeScene(scene) {
        disposeReflections(scene);
        hideSuspension(scene);
      });
      this.background.removeFromParent();
      this.background.geometry.dispose();
      this.background.material.dispose();
      this.scenes.clear();
      renderer.render = original;
      pipelines.delete(renderer);
      delete renderer.userData.underwaterPipeline;
      if (globalThis.__underwaterOptics === this) delete globalThis.__underwaterOptics;
    }
  };
  renderer.render = function renderWithEffects(scene, camera) {
    if (state.busy || renderer.getRenderTarget() || !scene?.isScene) return original(scene, camera);
    if (legacyWaterLook(renderer)) {
      if (state.optics) leaveOptics(state, scene, camera, renderer);
      state.optics = false;
      return original(scene, camera);
    }
    state.optics = true;
    return renderOptics(state, original, scene, camera);
  };
  renderer.userData ??= {};
  renderer.userData.underwaterPipeline = state;
  // Diagnostics for the review tools (exposure readout); not used by the app itself.
  globalThis.__underwaterOptics = state;
  pipelines.set(renderer, state);
  return state;
}
