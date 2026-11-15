// Hand-controller vibration is a preference: it does not change vehicle physics, so it is preset-neutral.
// Single source of truth is padHaptics; the old rov.input.v1 `haptics` mute is migrated once then dropped.
import {registerFidelityItem, getFidelity} from '../fidelity.js';

const STRINGS = {
  padHaptics: '手把震動',
  padHapticsHelp: '碰撞與纜線張力等事件的震動回饋。不支援的裝置會靜默略過。'
};
export const PAD_HAPTICS_ID = 'padHaptics';

registerFidelityItem({
  id: PAD_HAPTICS_ID,
  descriptionKey: 'padHapticsHelp',
  type: 'toggle',
  defaults: {real: true, assisted: true},
  presetNeutral: true
}, STRINGS);

export function padHapticsEnabled(fidelity = getFidelity()) {
  return fidelity.get(PAD_HAPTICS_ID) !== false;
}

/** Move the legacy mixer mute `settings.haptics` into padHaptics, then delete the old key. */
export function migratePadHapticsFromInput(settings, fidelity = getFidelity()) {
  if (!settings || !Object.prototype.hasOwnProperty.call(settings, 'haptics')) return false;
  const enabled = settings.haptics !== false;
  delete settings.haptics;
  if (!enabled) fidelity.set(PAD_HAPTICS_ID, false);
  return true;
}
