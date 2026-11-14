// Optional AI vision overlay for the onboard view: boxes, classes and confidence from a pluggable detector.
// It never changes photo evidence or scoring authority. Whether it is shown is the `aiOverlay` fidelity item
// (off in `real`: oracle detection exceeds the real vehicle); keys come from input/bindings.js (`visionToggle`,
// `visionMark`) and the engineering drawer carries pointer buttons. The overlay canvas sits on --z-scene-mark.
import {inspectObservation} from '../observation_camera.js';
import {registerFidelityItem, getFidelity} from '../fidelity.js';
import {OracleDetector, OnnxDetector, RemoteDetector} from './detector.js';

const STRINGS = {
  toggle: 'AI 視覺',
  available: '畫面中有可登錄目標',
  mark: '標記偵測目標',
  confirm: '請先在機載畫面確認偵測目標再拍照。',
  oracle: 'Oracle · 模擬真值',
};
export const VISION_ITEM = 'aiOverlay';

registerFidelityItem({
  id: VISION_ITEM, labelKey: VISION_ITEM, descriptionKey: 'aiOverlayHelp', type: 'toggle',
  defaults: {real: false, assisted: true}, exceedsReal: true,
  urlValue: function fromUrl(params) {
    return params.has('vision') ? true : undefined;
  },
}, {aiOverlay: 'AI 疊圖', aiOverlayHelp: '在機載畫面上標示辨識結果（預設為模擬真值，非實際模型）。'});

export function drawDetections(ctx, detections, width, height) {
  ctx.strokeStyle = '#4fd1e0';
  ctx.fillStyle = '#e8f1f5';
  ctx.font = '13px monospace';
  for (const detection of detections) {
    const [x, y, w, h] = detection.box;
    ctx.strokeRect(x * width, y * height, w * width, h * height);
    const label = `${detection.cls} ${(detection.score * 100).toFixed(0)}%`;
    ctx.fillText(label, x * width, Math.max(14, y * height - 4));
  }
}

function unit(value) {
  return Math.max(0, Math.min(1, Number(value) || 0));
}

// The documented wire form: normalized top-left xywh clipped to the frame (targets can extend past the edge).
function wireDetection(detection) {
  const x = unit(detection.box[0]);
  const y = unit(detection.box[1]);
  const right = unit(detection.box[0] + detection.box[2]);
  const bottom = unit(detection.box[1] + detection.box[3]);
  return {cls: detection.cls, score: unit(detection.score), box: [x, y, right - x, bottom - y]};
}

function drawerButton(text, onclick) {
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = text;
  button.onclick = onclick;
  document.querySelector('.mission-tools')?.append(button);
  return button;
}

// Seeded per-pixel noise for dataset captures; no effect when `amount` is zero.
function addNoise(rgb, width, height, amount, seed) {
  if (!amount) return;
  const pixels = rgb.getImageData(0, 0, width, height);
  let state = seed || 13;
  for (let i = 0; i < pixels.data.length; i += 4) {
    state = (1664525 * state + 1013904223) >>> 0;
    const noise = (state / 4294967296 - .5) * amount;
    for (let channel = 0; channel < 3; channel++) pixels.data[i + channel] += noise;
  }
  rgb.putImageData(pixels, 0, 0);
}

export function installVision({send, canvas, getContext}) {
  const fidelity = getFidelity();
  const overlay = document.createElement('canvas');
  overlay.id = 'vision-overlay';
  Object.assign(overlay.style, {position: 'fixed', pointerEvents: 'none', zIndex: 'var(--z-scene-mark)'});
  document.body.append(overlay);
  let detector = new OracleDetector();
  let hz = 10;
  const api = {detections: [], truth: [], overlay};
  Object.defineProperty(api, 'enabled', {
    get: function enabled() {
      return fidelity.get(VISION_ITEM) === true;
    },
    set: function setEnabled(value) {
      fidelity.set(VISION_ITEM, !!value);
    },
  });
  function toggle() {
    api.enabled = !api.enabled;
  }
  function markTarget() {
    const target = api.detections.find(detection => detection.entity_id);
    if (target) send({type: 'operation', action: 'expedition_mark', entity_id: target.entity_id});
  }
  // The engineering drawer is built after this module, so its buttons are added on first use.
  let mark = null;
  function ensureButtons() {
    if (mark || !document.querySelector('.mission-tools')) return;
    drawerButton(STRINGS.toggle, toggle);
    mark = drawerButton(STRINGS.mark, markTarget);
    mark.hidden = true;
  }
  let tracked = [];
  let shown = false;
  let last = -Infinity;
  let busy = false;
  function clear(ctx) {
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    api.detections = [];
    if (mark) mark.hidden = true;
    tracked = [];
  }
  async function infer(context, now) {
    busy = true;
    last = now;
    const start = performance.now();
    try {
      api.truth = inspectObservation({...context, all: true});
      api.detections = await detector.detect({truth: api.truth, canvas, image: canvas.toDataURL('image/jpeg'),
        width: canvas.width, height: canvas.height});
      send({type: 'vision_results', detections: api.detections.slice(0, 256).map(wireDetection)});
      api.latency = performance.now() - start;
      if (api.latency > 100 && !(detector instanceof OracleDetector)) hz = Math.max(2, hz / 2);
      if (api.latency > 500 && !(detector instanceof OracleDetector)) api.configure({mode: 'oracle'});
    } catch (error) {
      api.error = String(error);
      api.configure({mode: 'oracle'});
    } finally {
      busy = false;
    }
  }
  // Resizing a canvas reallocates it, so only do it when the viewport actually changed.
  function fit(rect) {
    if (overlay.width !== Math.round(rect.width)) overlay.width = rect.width;
    if (overlay.height !== Math.round(rect.height)) overlay.height = rect.height;
    overlay.style.left = `${rect.left}px`;
    overlay.style.top = `${rect.top}px`;
  }
  // Per frame. While the overlay is off nothing is projected or redrawn, so it costs the frame nothing.
  api.update = function update(now) {
    ensureButtons();
    const ctx = overlay.getContext('2d');
    const context = api.enabled ? getContext() : null;
    if (!context || context.camMode !== 'onboard') {
      if (shown) clear(ctx);
      shown = false;
      return;
    }
    shown = true;
    context.targets = [...context.targets, ...(api.extraTargets || [])];
    const rect = canvas.getBoundingClientRect();
    fit(rect);
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    if (!busy && now - last >= 1000 / hz) infer(context, now);
    tracked = api.detections.map(function smooth(detection) {
      const previous = tracked.find(item => detection.entity_id && item.entity_id === detection.entity_id);
      const box = detection.box.map((value, i) => previous ? previous.box[i] * .6 + value * .4 : value);
      return {...detection, box};
    });
    if (mark) mark.hidden = !api.detections.some(detection => detection.entity_id);
    drawDetections(ctx, tracked, rect.width, rect.height);
    ctx.fillText(`${api.mode || STRINGS.oracle} · ${api.latency?.toFixed(1) || 0} ms · ${hz.toFixed(0)} Hz`, 24, 90);
    if (api.detections.length) ctx.fillText(STRINGS.available, 24, 112);
  };
  api.configure = function configure({mode = 'oracle', frequency = 10, ...config} = {}) {
    detector.dispose?.();
    detector = mode === 'onnx' ? new OnnxDetector(config)
      : mode === 'remote' ? new RemoteDetector(config.url) : new OracleDetector(config);
    api.mode = mode;
    hz = Math.max(1, Math.min(30, frequency));
  };
  api.requireAI = new URLSearchParams(location.search).has('vision-confirm-photo');
  api.assertPhoto = function assertPhoto() {
    if (api.requireAI && !api.detections.some(detection => detection.score >= .5)) throw Error(STRINGS.confirm);
  };
  api.setCurrent = current => send({type: 'current', ...current});
  // Dataset capture: perturb the view, render, extract labels in the same task, then restore everything.
  api.capture = function capture(options = {}) {
    const context = getContext();
    context.targets = [...context.targets, ...(api.extraTargets || [])];
    const originalPosition = context.camera.position.clone();
    const originalQuaternion = context.camera.quaternion.clone();
    const originalFog = context.scene.fog?.clone();
    if (options.pose) {
      context.camera.position.fromArray(options.pose.position);
      context.camera.quaternion.fromArray(options.pose.quaternion);
    }
    if (options.depthOffset) context.camera.position.y -= options.depthOffset;
    if (options.visibility) {
      context.world = {...context.world, scenario: {...context.world.scenario, visibility_m: options.visibility}};
      if (context.scene.fog) context.scene.fog.far = options.visibility;
    }
    context.state = {...context.state, silt: options.silt || 0};
    const lights = [];
    context.scene.traverse(function scaleLight(node) {
      if (!node.isSpotLight) return;
      lights.push([node, node.intensity]);
      node.intensity *= options.light ?? 1;
    });
    context.scene.updateMatrixWorld(true);
    const truth = inspectObservation({...context, all: true});
    context.renderer.render(context.scene, context.camera);
    const output = document.createElement('canvas');
    output.width = canvas.width;
    output.height = canvas.height;
    const rgb = output.getContext('2d');
    rgb.drawImage(canvas, 0, 0);
    addNoise(rgb, output.width, output.height, options.noise, options.seed);
    const image = output.toDataURL('image/png');
    context.camera.position.copy(originalPosition);
    context.camera.quaternion.copy(originalQuaternion);
    if (originalFog) context.scene.fog = originalFog;
    for (const [light, intensity] of lights) light.intensity = intensity;
    return {truth, image, width: canvas.width, height: canvas.height};
  };
  // Keys and pad sources are declared in input/bindings.js; this module supplies only the behaviour.
  api.bindInput = function bindInput(input) {
    ensureButtons();
    input.registerActions({
      visionToggle: {label: STRINGS.toggle, run: toggle},
      visionMark: {label: STRINGS.mark, enabled: () => api.enabled, run: markTarget},
    });
  };
  window.rovVision = api;
  return api;
}
