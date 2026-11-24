// Training mode forces real-vehicle fidelity for the dive, without permanently
// wiping the trainee's stored custom settings. Leaving real mid-session still
// prompts and is recorded on the scorecard (S6).

import {getFidelity, PRESET_NAMES} from '../fidelity.js';
import {localize} from '../i18n/index.js';
import {recordFidelityChange} from './metrics.js';

const STRINGS = localize('training.fidelity_guard', {
  leaveReal: '訓練模式預設真實擬真。切到輔助會記在成績單上，確定要切換嗎？',
  banner: '訓練模式：真實擬真',
  bannerAssist: '訓練模式：已離開真實擬真（將記在成績單）',
});

function forceRealItems(fidelity) {
  for (const item of fidelity.items()) {
    if (item.presetNeutral) continue;
    const target = item.defaults.real;
    if (fidelity.get(item.id) !== target) fidelity.set(item.id, target);
  }
}

export function restoreFidelitySnapshot(fidelity, prior) {
  if (!fidelity || !prior) return;
  const base = PRESET_NAMES.includes(prior.base) ? prior.base : 'real';
  fidelity.setPreset(base);
  for (const [id, value] of Object.entries(prior.values || {})) {
    if (value === undefined) continue;
    if (fidelity.get(id) !== value) fidelity.set(id, value);
  }
}

// Snapshot the trainee's settings, then override only non-preference items to real.
// Returns the snapshot so the caller can restore after the dive.
export function applyTrainingFidelityDefault(fidelity = getFidelity()) {
  if (!fidelity) return null;
  const prior = fidelity.snapshot();
  if (fidelity.preset !== 'real') forceRealItems(fidelity);
  return prior;
}

export function installTrainingFidelityGuard({
  metricsRef,
  onBanner,
  fidelity = getFidelity(),
} = {}) {
  const prior = applyTrainingFidelityDefault(fidelity);
  let armed = true;

  function refreshBanner() {
    const left = fidelity.preset !== 'real';
    onBanner?.(left ? STRINGS.bannerAssist : STRINGS.banner, left);
  }

  const unsubscribe = fidelity.subscribe(function onChange() {
    if (!armed) return;
    const preset = fidelity.preset;
    if (preset !== 'real') {
      const ok = globalThis.confirm?.(STRINGS.leaveReal);
      if (!ok) {
        armed = false;
        forceRealItems(fidelity);
        armed = true;
        refreshBanner();
        return;
      }
      if (metricsRef?.current) {
        recordFidelityChange(metricsRef.current, {preset, assisted: true});
      }
    } else if (metricsRef?.current) {
      recordFidelityChange(metricsRef.current, {preset: 'real'});
    }
    refreshBanner();
  });

  refreshBanner();
  return {
    dispose() {
      armed = false;
      unsubscribe?.();
      armed = false;
      restoreFidelitySnapshot(fidelity, prior);
    },
    refreshBanner,
    prior,
  };
}
