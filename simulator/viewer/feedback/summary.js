// Ring buffer of recent flight state, FPS samples, server log lines and console errors for bug reports.
// Never stores player names, emails, tokens or other personal data.
import { getFidelity } from '../fidelity.js';
import { getDisplayPrefs } from '../prefs/display.js';
import { getLanguage } from '../i18n/index.js';

const WINDOW_MS = 60_000;
const MAX_SAMPLES = 120;
const MAX_LOG = 80;
const MAX_ERRORS = 40;

function nowMs() {
  return performance.now();
}

function trimWindow(list, stamp, onDrop = null) {
  const floor = stamp - WINDOW_MS;
  while (list.length && list[0].at < floor) {
    const dropped = list.shift();
    onDrop?.(dropped);
  }
}

function scrubText(value) {
  return String(value ?? '')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[redacted-email]')
    .replace(/\b(?:sk|pk|tok|token|bearer)[-_A-Za-z0-9.]{8,}\b/gi, '[redacted-token]')
    .slice(0, 500);
}

function webglRenderer() {
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (!gl) return null;
    const info = gl.getExtension('WEBGL_debug_renderer_info');
    if (!info) return gl.getParameter(gl.RENDERER) || null;
    return gl.getParameter(info.UNMASKED_RENDERER_WEBGL) || null;
  } catch {
    return null;
  }
}

export function createSummaryBuffer() {
  const samples = [];
  const fpsSamples = [];
  const serverLog = [];
  const consoleErrors = [];
  const seenLogKeys = new Set();
  let gamepadId = '';
  const originalError = console.error.bind(console);

  function rememberError(message, source = 'console') {
    const stamp = nowMs();
    consoleErrors.push({ at: stamp, source, message: scrubText(message) });
    trimWindow(consoleErrors, stamp);
    while (consoleErrors.length > MAX_ERRORS) consoleErrors.shift();
  }

  console.error = function reportConsoleError(...args) {
    rememberError(args.map((part) => (part instanceof Error ? part.stack || part.message : part)).join(' '));
    return originalError(...args);
  };
  addEventListener('error', function onWindowError(event) {
    rememberError(event.message || event.error?.message || 'error', 'window');
  });
  addEventListener('unhandledrejection', function onRejection(event) {
    const reason = event.reason;
    rememberError(reason instanceof Error ? reason.stack || reason.message : reason, 'rejection');
  });
  document.addEventListener('rov-input-device', function onDevice(event) {
    if (typeof event.detail === 'string' && event.detail) gamepadId = event.detail;
  });

  function sample({ state, world, performanceInfo, quality }) {
    const stamp = nowMs();
    const entry = {
      at: stamp,
      t: state?.t ?? null,
      depth: state?.depth ?? state?.pos?.[2] ?? null,
      locked: !!state?.locked,
      paused: !!state?.paused,
      scenario: world?.scenario?.key || state?.scenario || null,
      mission: state?.mission?.mode || null,
      modelId: state?.model_id || null,
      vehicleId: state?.vehicle_id || null,
      operationMode: state?.operation_mode || null,
      assist: state?.assist ? {
        level: state.assist.level,
        profile: state.assist.profile,
        holding: state.assist.holding,
      } : null,
      pos: Array.isArray(state?.pos) ? state.pos.map(Number) : null,
    };
    samples.push(entry);
    trimWindow(samples, stamp);
    while (samples.length > MAX_SAMPLES) samples.shift();

    const fps = performanceInfo?.fps;
    if (Number.isFinite(fps)) {
      fpsSamples.push({ at: stamp, fps, scale: performanceInfo?.scale ?? null });
      trimWindow(fpsSamples, stamp);
    }

    const lines = Array.isArray(state?.log) ? state.log : [];
    for (const line of lines.slice(-20)) {
      const key = `${line.t ?? ''}|${line.stamp ?? ''}|${line.text ?? ''}`;
      if (seenLogKeys.has(key)) continue;
      seenLogKeys.add(key);
      serverLog.push({
        key,
        at: stamp,
        t: line.t ?? null,
        stamp: line.stamp ?? null,
        text: scrubText(line.text),
      });
    }
    function dropLog(entry) {
      if (entry?.key) seenLogKeys.delete(entry.key);
    }
    trimWindow(serverLog, stamp, dropLog);
    while (serverLog.length > MAX_LOG) dropLog(serverLog.shift());

    return { quality };
  }

  function build({ category, description, quality, performanceInfo }) {
    const fidelity = getFidelity().snapshot();
    const display = getDisplayPrefs();
    const latest = samples.at(-1) || {};
    const fpsValues = fpsSamples.map((row) => row.fps).filter(Number.isFinite);
    const fpsStats = fpsValues.length ? {
      current: performanceInfo?.fps ?? fpsValues.at(-1) ?? null,
      min: Math.min(...fpsValues),
      max: Math.max(...fpsValues),
      avg: Math.round(fpsValues.reduce((sum, value) => sum + value, 0) / fpsValues.length),
      samples: fpsSamples.slice(-60),
    } : { current: performanceInfo?.fps ?? null, samples: [] };
    return {
      version: 1,
      createdAt: new Date().toISOString(),
      category,
      description: scrubText(description).slice(0, 280),
      privacy: 'local-only; no automatic upload; no personal identifiers',
      session: {
        scenario: latest.scenario,
        mission: latest.mission,
        modelId: latest.modelId,
        vehicleId: latest.vehicleId,
        operationMode: latest.operationMode,
        t: latest.t,
        depth: latest.depth,
        locked: latest.locked,
        paused: latest.paused,
        assist: latest.assist,
      },
      fidelity,
      quality: quality || null,
      display: {
        language: getLanguage(),
        fpsCap: display.get('fpsCap'),
        units: display.get('units'),
        uiScale: display.get('uiScale'),
      },
      device: {
        platform: navigator.platform || null,
        language: navigator.language || null,
        languages: Array.from(navigator.languages || []).slice(0, 4),
        hardwareConcurrency: navigator.hardwareConcurrency || null,
        deviceMemory: navigator.deviceMemory || null,
        webgl: webglRenderer(),
        gamepadId: gamepadId || null,
        desktop: !!globalThis.window?.rovDesktop,
      },
      fps: fpsStats,
      serverLog: serverLog.slice(-MAX_LOG).map(function publicLog(entry) {
        return { at: entry.at, t: entry.t, stamp: entry.stamp, text: entry.text };
      }),
      consoleErrors: consoleErrors.slice(-MAX_ERRORS),
      samples: samples.slice(-MAX_SAMPLES),
    };
  }

  function dispose() {
    console.error = originalError;
  }

  return { sample, build, dispose, WINDOW_MS };
}
