// Scene post-processing, independent of camera simulation. Real optics stay in material shaders.
// T14b may register a camera pass; capture paths share the renderer's screen hook.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { updateReflections, disposeReflections } from './reflections.js';
import { updateWaterSurface, disposeWaterSurface } from './surface.js';
import { updateSuspension } from './suspension.js';
import { renderQualityState } from '../render_quality.js';

const pipelines = new WeakMap();
const finish = {
  uniforms: { tDiffuse: { value: null }, strength: { value: 0 } },
  vertexShader: `varying vec2 vUv;
    void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float strength; varying vec2 vUv;
    void main() {
      vec4 c = texture2D(tDiffuse, vUv);
      float edge = smoothstep(0.2, 0.72, length(vUv - 0.5));
      c.rgb *= 1.0 - strength * 0.12 * edge;
      gl_FragColor = c;
    }`
};

export function installUnderwaterPipeline(renderer, { surface = null } = {}) {
  if (pipelines.has(renderer)) return pipelines.get(renderer);
  if (['performance', 'low'].includes(renderQualityState(renderer)?.mode)) return null;
  const original = renderer.render.bind(renderer);
  const state = {
    background: new THREE.Color(), fog: new THREE.Color(),
    scenes: new Set(), composer: null, busy: false, cameraPass: null, width: 0, height: 0,
    // No enhancement is enabled by default, including internal training and photography.
    enhancements: new URLSearchParams(location.search).get('beautify') === '1',
    setEnhancements: function setEnhancements(enabled) { this.enhancements = !!enabled; },
    setCameraPass: function setCameraPass(pass) {
      if (this.cameraPass && this.composer) this.composer.removePass(this.cameraPass);
      this.cameraPass = pass;
      if (pass && this.composer) this.composer.insertPass(pass, 1);
    },
    dispose: function dispose() {
      this.composer?.passes.filter(pass => pass !== this.cameraPass)
        .forEach(function disposePass(pass) { pass.dispose?.(); });
      this.composer?.dispose();
      disposeWaterSurface(surface);
      this.scenes.forEach(disposeReflections);
      this.scenes.clear();
      renderer.render = original;
      pipelines.delete(renderer);
      delete renderer.userData.underwaterPipeline;
    }
  };
  renderer.render = function renderWithEffects(scene, camera) {
    if (state.busy || renderer.getRenderTarget()) return original(scene, camera);
    const quality = renderQualityState(renderer);
    const low = ['performance', 'low'].includes(quality?.mode);
    if (low) {
      if (state.wasLow === false) {
        updateWaterSurface(surface, camera, scene, true);
        updateSuspension(scene, camera, renderer, quality);
        updateReflections(scene, quality.mode);
      }
      state.wasLow = true;
      return original(scene, camera);
    }
    state.wasLow = false;
    const background = scene.background?.isColor ? scene.background : null;
    const fog = scene.fog?.color;
    if (background) state.background.copy(background);
    if (fog) state.fog.copy(fog);
    // Ambient water radiance fades with sunlight; lamp lighting remains independent.
    const radiance = 0.003 + 0.997 * Math.exp(-Math.max(0, -camera.position.y) / 7);
    if (background) background.multiplyScalar(radiance);
    if (fog) fog.multiplyScalar(radiance);
    try {
      if (!state.busy && !renderer.getRenderTarget()) {
        state.scenes.add(scene);
        updateReflections(scene, quality?.mode);
        updateWaterSurface(surface, camera, scene, ['performance', 'low'].includes(quality?.mode),
          state.enhancements);
        updateSuspension(scene, camera, renderer, quality);
      }
      const supported = quality?.mode !== 'performance' && quality?.mode !== 'low' && !quality?.effectsSuppressed;
      if (state.busy || renderer.getRenderTarget() || !supported || (!state.enhancements && !state.cameraPass)) {
        return original(scene, camera);
      }
      if (!state.composer) {
        state.composer = new EffectComposer(renderer);
        state.renderPass = new RenderPass(scene, camera);
        state.finishPass = new ShaderPass(finish);
        state.composer.addPass(state.renderPass);
        if (state.cameraPass) state.composer.addPass(state.cameraPass);
        state.composer.addPass(state.finishPass);
        state.composer.addPass(new OutputPass());
      }
      const size = renderer.getDrawingBufferSize(new THREE.Vector2());
      if (size.x !== state.width || size.y !== state.height) {
        state.composer.setPixelRatio(1);
        state.composer.setSize(size.x, size.y);
        state.width = size.x;
        state.height = size.y;
      }
      state.renderPass.scene = scene;
      state.renderPass.camera = camera;
      state.finishPass.uniforms.strength.value = state.enhancements ? 1 : 0;
      state.busy = true;
      try { state.composer.render(); } finally { state.busy = false; }
    } finally {
      if (background) background.copy(state.background);
      if (fog) fog.copy(state.fog);
    }
  };
  renderer.userData ??= {};
  renderer.userData.underwaterPipeline = state;
  pipelines.set(renderer, state);
  return state;
}
