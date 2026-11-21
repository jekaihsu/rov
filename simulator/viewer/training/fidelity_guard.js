// Training mode defaults to the real fidelity preset. Leaving real shows a
// confirm prompt and is recorded on the scorecard (S6).

import {getFidelity} from '../fidelity.js';
import {localize} from '../i18n/index.js';
import {recordFidelityChange} from './metrics.js';

const STRINGS = localize('training.fidelity_guard', {
  leaveReal: '訓練模式預設真實擬真。切到輔助會記在成績單上，確定要切換嗎？',
  banner: '訓練模式：真實擬真',
  bannerAssist: '訓練模式：已離開真實擬真（將記在成績單）',
});

export function applyTrainingFidelityDefault(fidelity = getFidelity()) {
  if (!fidelity) return;
  if (fidelity.preset !== 'real') fidelity.setPreset('real');
}

export function installTrainingFidelityGuard({metricsRef, onBanner} = {}) {
  const fidelity = getFidelity();
  applyTrainingFidelityDefault(fidelity);
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
        fidelity.setPreset('real');
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
    },
    refreshBanner,
  };
}
