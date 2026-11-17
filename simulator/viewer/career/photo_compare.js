// Same-angle photo compare for deliverables with compare:{yaw_tol_deg,standoff_tol_m} and optional
// reference:{yaw_deg,standoff_m}. Pure comparePose uses aim() from the tracker; the optional ghost-frame
// overlay is an assisted-only fidelity item (exceedsReal) because a real pilot has no on-screen guide.

import { registerFidelityItem, getFidelity } from '../fidelity.js';
import { localize } from '../i18n/core.js';
import { aim } from './deliverables.js';

const STRINGS = localize('career.photo_compare', {
  assist: '同角度輔助框',
  assistHelp: '在機載畫面顯示上次拍攝的參考框。真機沒有這個疊圖。',
  hint: '對齊參考角度',
  drift: '角度偏離',
});

export const PHOTO_COMPARE_ASSIST = 'photoCompareAssist';

function isOn(value) {
  return value === true;
}

registerFidelityItem({
  id: PHOTO_COMPARE_ASSIST,
  descriptionKey: 'assistHelp',
  type: 'toggle',
  defaults: { real: false, assisted: true },
  exceedsReal: true,
  exceeds: isOn,
}, { photoCompareAssist: STRINGS.assist, assistHelp: STRINGS.assistHelp });

function vector(value) {
  return Array.isArray(value) && value.length >= 3 ? value.map(Number) : null;
}

function distance(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

function wrapDegrees(value) {
  return ((value + 540) % 360) - 180;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

/**
 * Compare current pose to the deliverable's reference / facing target.
 * Returns {ok, yawErr, standoffErr, score} with score in 0–1.
 */
export function comparePose(itemDef, state) {
  const raw = itemDef?.compare;
  if (!raw) return { ok: true, yawErr: 0, standoffErr: 0, score: 1 };
  const compare = raw === true ? {} : raw;
  const pos = vector(state?.pos);
  const point = vector(itemDef.point);
  if (!pos || !point) return { ok: false, yawErr: 180, standoffErr: Infinity, score: 0 };
  const gap = distance(pos, point);
  const ref = itemDef.reference || {};
  const yawRef = Number.isFinite(Number(ref.yaw_deg))
    ? Number(ref.yaw_deg)
    : (Number.isFinite(Number(ref.heading_deg)) ? Number(ref.heading_deg) : null);
  let yawErr;
  if (yawRef != null) {
    const heading = Number(state.euler?.[2]) || 0;
    yawErr = Math.abs(wrapDegrees(heading - yawRef));
  } else {
    yawErr = aim(state, point).yaw;
  }
  const near = Number(itemDef.standoff?.[0]);
  const far = Number(itemDef.standoff?.[1]);
  const mid = Number.isFinite(near) && Number.isFinite(far) ? (near + far) / 2 : 2;
  const refStand = Number(ref.standoff_m);
  const refRange = Array.isArray(ref.standoff)
    ? (Number(ref.standoff[0]) + Number(ref.standoff[1])) / 2
    : NaN;
  const ideal = Number.isFinite(refStand) ? refStand : (Number.isFinite(refRange) ? refRange : mid);
  const standoffErr = Math.abs(gap - ideal);
  const yawTol = Number(compare.yaw_tol_deg);
  const gapTol = Number(compare.standoff_tol_m);
  const yawLimit = Number.isFinite(yawTol) ? yawTol : 15;
  const gapLimit = Number.isFinite(gapTol) ? gapTol : 0.75;
  const ok = yawErr <= yawLimit && standoffErr <= gapLimit;
  const yawScore = Math.max(0, 1 - yawErr / Math.max(yawLimit, 1e-6));
  const gapScore = Math.max(0, 1 - standoffErr / Math.max(gapLimit, 1e-6));
  const score = (yawScore + gapScore) / 2;
  return { ok, yawErr, standoffErr, score };
}

/** Optional ghost frame; only drawn when the photoCompareAssist fidelity item is on. */
export function installPhotoCompareOverlay() {
  const root = element('div', 'photo-compare');
  root.hidden = true;
  const frame = element('div', 'photo-compare-frame');
  const label = element('p', 'photo-compare-label', STRINGS.hint);
  root.append(frame, label);
  document.body.append(root);

  function update(itemDef, state) {
    const fidelity = getFidelity();
    const enabled = fidelity.get(PHOTO_COMPARE_ASSIST) === true;
    if (!enabled || !itemDef?.compare) {
      root.hidden = true;
      return null;
    }
    const result = comparePose(itemDef, state);
    root.hidden = false;
    root.dataset.ok = result.ok ? 'true' : 'false';
    label.textContent = result.ok ? STRINGS.hint : STRINGS.drift;
    return result;
  }

  function dispose() {
    root.remove();
  }

  return { update, dispose };
}
