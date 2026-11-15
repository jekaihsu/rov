// Assisted-only highlight: when a tether is hooked, boost the cable colour near each snag point so the
// pilot can see where tension concentrates. Real vehicles have no underwater cable view — only the
// tension gauges and the tether-hand radio — so this item stays off in `real`.
import {getFidelity, registerFidelityItem} from '../fidelity.js';
import {tensionColor, warnLoad} from './tension.js';

const STRINGS = {
  snagFocus: '勾點張力集中',
  snagFocusHelp: '勾纏時在勾點附近加亮纜線張力。真機看不到水下纜線，只能靠張力讀數與纜線手無線電；預設關閉。',
};
const FOCUS_RADIUS_M = 1.25;

registerFidelityItem({
  id: 'snagFocus', descriptionKey: 'snagFocusHelp', type: 'toggle',
  defaults: {real: false, assisted: true}, exceedsReal: true,
  exceeds: (value) => value === true,
}, {snagFocus: STRINGS.snagFocus, snagFocusHelp: STRINGS.snagFocusHelp});

export function snagFocusEnabled(fidelity = getFidelity()) {
  return !!fidelity.get('snagFocus');
}

/** Tension used for colouring along the cable. Without focus this is the spool→ROV linear blend. */
export function tensionAlong(tether, s, points) {
  const spool = tether?.tension_spool || 0;
  const rov = tether?.tension_rov || 0;
  let tension = spool + (rov - spool) * s;
  if (!snagFocusEnabled() || !points?.length) return tension;
  const snags = tether?.snags || [];
  if (!snags.length) return tension;
  const index = Math.min(points.length - 1, Math.max(0, Math.round(s * (points.length - 1))));
  const sample = points[index];
  for (const snag of snags) {
    if (!snag?.held || !snag.point) continue;
    // Snag points are NED; cable points are already in three.js space from the viewer.
    const dx = sample.x - (-snag.point[1]);
    const dy = sample.y - (-snag.point[2]);
    const dz = sample.z - snag.point[0];
    const distance = Math.hypot(dx, dy, dz);
    if (distance >= FOCUS_RADIUS_M) continue;
    const weight = 1 - distance / FOCUS_RADIUS_M;
    const peak = snag.tension_n || tether.tension_max || tension;
    tension = Math.max(tension, peak * (0.55 + 0.45 * weight));
  }
  return tension;
}

/** Colour callback for the cable tube / polyline: applies focus when the fidelity item is on. */
export function cableTensionColor(tether, s, points, out) {
  const warnN = warnLoad(tether);
  let tension = tensionAlong(tether, s, points);
  if (tether?.warn) tension = Math.max(tension, warnN);
  return tensionColor(tension, out, warnN);
}
