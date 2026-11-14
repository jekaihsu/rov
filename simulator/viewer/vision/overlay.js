// Optional engineering vision overlay; never changes photographic scoring authority.
import {inspectObservation} from '../observation_camera.js';
import {OracleDetector, OnnxDetector, RemoteDetector} from './detector.js';
const STRINGS = {toggle: 'AI 视觉（N）', available: '画面中有可登录目标', mark: '标记检测（M）', confirm: '请先在机载画面确认检测目标再拍照。', oracle: 'Oracle · 模拟真值'};

export function drawDetections(ctx, detections, width, height) {
  ctx.strokeStyle = '#4fd1e0';
  ctx.fillStyle = '#e8f1f5';
  ctx.font = '13px monospace';
  for (const detection of detections) {
    const [x, y, w, h] = detection.box;
    ctx.strokeRect(x * width, y * height, w * width, h * height);
    ctx.fillText(`${detection.cls} ${(detection.score * 100).toFixed(0)}%`, x * width, Math.max(14, y * height - 4));
  }
}

export function installVision({send,canvas, getContext}) {
  const overlay = document.createElement('canvas');
  overlay.id = 'vision-overlay';
  Object.assign(overlay.style, {position: 'fixed', pointerEvents: 'none', zIndex: 4});
  document.body.append(overlay);
  const button = document.createElement('button');
  button.textContent = STRINGS.toggle;
  Object.assign(button.style, {position: 'fixed', top: '160px', right: '4%', zIndex: 20});
  document.body.append(button);
  let detector = new OracleDetector();
  let hz = 10;
  const api = {enabled: new URLSearchParams(location.search).has('vision'), detections: [], truth: [], overlay};
  button.onclick = () => { api.enabled = !api.enabled; };
  window.addEventListener('keydown', event => {
    if (event.code === 'KeyN' && !/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) button.click();
  });
  const mark = document.createElement('button');
  mark.textContent = STRINGS.mark;
  Object.assign(mark.style, {position: 'fixed', top: '200px', right: '4%', zIndex: 20});
  mark.onclick = () => {
    const target = api.detections.find(detection => detection.entity_id);
    if (target) send({type: 'operation', action: 'expedition_mark', entity_id: target.entity_id});
  };
  document.body.append(mark);
  window.addEventListener('keydown', event => {
    if (event.code === 'KeyM' && !/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) mark.click();
  });
  let tracked = [];
  let last = -Infinity;
  let busy = false;
  api.update = async now => {
    const context = getContext();
    context.targets = [...context.targets, ...(api.extraTargets || [])];
    const rect = canvas.getBoundingClientRect();
    overlay.width = rect.width;
    overlay.height = rect.height;
    overlay.style.left = `${rect.left}px`;
    overlay.style.top = `${rect.top}px`;
    const ctx = overlay.getContext('2d');
    if (!api.enabled || context.camMode !== 'onboard') {
      api.detections = [];
      mark.hidden = true;
      tracked = [];
      return;
    }
    if (!busy && now - last >= 1000 / hz) {
      busy = true;
      last = now;
      const start = performance.now();
      try {
        api.truth = inspectObservation({...context, all: true});
        api.detections = await detector.detect({truth: api.truth, canvas, image: canvas.toDataURL('image/jpeg'), width: canvas.width, height: canvas.height});
        send({type: 'vision_results', detections: api.detections});
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
    tracked = api.detections.map(detection => {
      const previous = tracked.find(item => detection.entity_id && item.entity_id === detection.entity_id);
      return {...detection, box: detection.box.map((value, i) => previous ? previous.box[i] * .6 + value * .4 : value)};
    });
    mark.hidden = !api.detections.some(detection => detection.entity_id);
    drawDetections(ctx, tracked, rect.width, rect.height);
    ctx.fillText(`${api.mode || STRINGS.oracle} · ${api.latency?.toFixed(1) || 0} ms · ${hz.toFixed(0)} Hz`, 24, 90);
    if (api.detections.length) ctx.fillText(STRINGS.available, 24, 112);
  };
  api.configure = ({mode = 'oracle', frequency = 10, ...config} = {}) => {
    detector.dispose?.();
    detector = mode === 'onnx' ? new OnnxDetector(config)
      : mode === 'remote' ? new RemoteDetector(config.url) : new OracleDetector(config);
    api.mode = mode;
    hz = Math.max(1, Math.min(30, frequency));
  };
  api.requireAI = new URLSearchParams(location.search).has('vision-confirm-photo');
  api.assertPhoto = () => {
    if (api.requireAI && !api.detections.some(detection => detection.score >= .5)) throw Error(STRINGS.confirm);
  };
  api.setCurrent = current => send({type: 'current', ...current});
  api.capture = (options = {}) => {
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
    context.scene.traverse(node => {
      if (node.isSpotLight) {
        lights.push([node, node.intensity]);
        node.intensity *= options.light ?? 1;
      }
    });
    context.scene.updateMatrixWorld(true);
    const truth = inspectObservation({...context, all: true});
    context.renderer.render(context.scene, context.camera);
    const output = document.createElement('canvas');
    output.width = canvas.width;
    output.height = canvas.height;
    const rgb = output.getContext('2d');
    rgb.drawImage(canvas, 0, 0);
    if (options.noise) {
      const pixels = rgb.getImageData(0, 0, output.width, output.height);
      let seed = options.seed || 13;
      for (let i = 0; i < pixels.data.length; i += 4) {
        seed = (1664525 * seed + 1013904223) >>> 0;
        const noise = (seed / 4294967296 - .5) * options.noise;
        for (let channel = 0; channel < 3; channel++) pixels.data[i + channel] += noise;
      }
      rgb.putImageData(pixels, 0, 0);
    }
    const image = output.toDataURL('image/png');
    context.camera.position.copy(originalPosition);
    context.camera.quaternion.copy(originalQuaternion);
    if (originalFog) context.scene.fog = originalFog;
    for (const [light, intensity] of lights) light.intensity = intensity;
    return {truth, image, width: canvas.width, height: canvas.height};
  };
  window.rovVision = api;
  return api;
}
