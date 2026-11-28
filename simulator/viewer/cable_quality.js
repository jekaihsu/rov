// Cable tube resolution for the live tether (presentation only). Lower tiers keep a readable yellow tube without
// rebuilding thousands of vertices every frame on integrated GPUs. Options follow the live render-quality mode so a
// mid-dive quality change takes effect on the next tube rebuild.

import {detectHardware, renderQualityState, subscribeRenderQuality} from './render_quality.js';

export function installCableTubeGate(cable, renderer) {
  const gate = createCableTubeGate({
    cable,
    getQuality: () => renderQualityState(renderer),
    detectHardware: () => detectHardware(renderer),
  });
  subscribeRenderQuality(gate.sync);
  return gate;
}

export function cableTubeOptions(mode = 'auto', {startsLow = false} = {}) {
  if (mode === 'high' || mode === 'ultra') {
    return {radius: 0.0065, segments: 240, radial: 8, colors: true};
  }
  if (mode === 'performance' || mode === 'low' || startsLow) {
    return {radius: 0.0065, segments: 96, radial: 5, colors: true};
  }
  return {radius: 0.0065, segments: 160, radial: 6, colors: true};
}

// How often the thick tube may rebuild (Hz). The thin polyline can stay at the display rate.
export function cableTubeHz(mode = 'auto', {startsLow = false} = {}) {
  if (mode === 'performance' || mode === 'low' || startsLow) return 20;
  if (mode === 'high' || mode === 'ultra') return 60;
  return 30;
}

function storedQualityMode() {
  try {
    return globalThis.localStorage?.getItem('rov.quality') || 'auto';
  } catch {
    return 'auto';
  }
}

/**
 * Keeps a Cable's tube options and rebuild rate in sync with render quality.
 * Call shouldRebuild(now) each tether frame; when true, call cable.update(...).
 *
 *   const tube = createCableTubeGate({cable, getQuality: () => renderQualityState(renderer),
 *     detectHardware: () => detectHardware(renderer)});
 */
export function createCableTubeGate({cable, getQuality, detectHardware}) {
  let lastKey = '';
  let nextAt = -Infinity;

  function sync() {
    const quality = getQuality?.() || null;
    const mode = quality?.mode || storedQualityMode();
    const hardware = quality?.hardware || detectHardware?.() || {};
    const opts = cableTubeOptions(mode, hardware);
    const key = `${mode}|${hardware.startsLow ? 1 : 0}|${opts.segments}|${opts.radial}`;
    if (key !== lastKey) {
      cable.setOptions(opts);
      lastKey = key;
      nextAt = -Infinity;
    }
    return cableTubeHz(mode, hardware);
  }

  function shouldRebuild(now = performance.now()) {
    const hz = sync();
    if (now - nextAt < 1000 / hz) return false;
    nextAt = now;
    return true;
  }

  sync();
  return {shouldRebuild, sync};
}
