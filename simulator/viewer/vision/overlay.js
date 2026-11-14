// Optional engineering vision overlay; never changes photographic scoring authority.
import {inspectObservation} from '../observation_camera.js';
import {OracleDetector} from './detector.js';
const STRINGS = {toggle: 'AI 视觉（N）', available: '画面中有可登录目标', oracle: 'Oracle · 模拟真值'};

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

export function installVision({canvas, getContext}) {
  const overlay = document.createElement('canvas');
  overlay.id = 'vision-overlay';
  Object.assign(overlay.style, {position: 'fixed', pointerEvents: 'none', zIndex: 4});
  document.body.append(overlay);
  const button = document.createElement('button');
  button.textContent = STRINGS.toggle;
  Object.assign(button.style, {position: 'fixed', bottom: '4%', right: '4%', zIndex: 20});
  document.body.append(button);
  const detector = new OracleDetector();
  const api = {enabled: new URLSearchParams(location.search).has('vision'), detections: [], truth: [], overlay};
  button.onclick = () => { api.enabled = !api.enabled; };
  window.addEventListener('keydown', event => {
    if (event.code === 'KeyN' && !/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) button.click();
  });
  let last = -Infinity;
  let busy = false;
  api.update = async now => {
    const context = getContext();
    const rect = canvas.getBoundingClientRect();
    overlay.width = rect.width;
    overlay.height = rect.height;
    overlay.style.left = `${rect.left}px`;
    overlay.style.top = `${rect.top}px`;
    const ctx = overlay.getContext('2d');
    if (!api.enabled || context.camMode !== 'onboard') {
      api.detections = [];
      return;
    }
    if (!busy && now - last >= 100) {
      busy = true;
      last = now;
      const start = performance.now();
      try {
        api.truth = inspectObservation({...context, all: true});
        api.detections = await detector.detect({truth: api.truth});
        api.latency = performance.now() - start;
      } finally {
        busy = false;
      }
    }
    drawDetections(ctx, api.detections, rect.width, rect.height);
    ctx.fillText(`${STRINGS.oracle} · ${api.latency?.toFixed(1) || 0} ms · 10 Hz`, 24, 90);
    if (api.detections.length) ctx.fillText(STRINGS.available, 24, 112);
  };
  api.capture = () => {
    const context = getContext();
    context.scene.updateMatrixWorld(true);
    return inspectObservation({...context, all: true});
  };
  window.rovVision = api;
  return api;
}
