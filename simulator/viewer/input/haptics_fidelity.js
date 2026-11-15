// Hand-controller vibration is a preference: it does not change vehicle physics, so it is preset-neutral.
import {registerFidelityItem, getFidelity} from '../fidelity.js';

const STRINGS = {
  padHaptics: '手把震動',
  padHapticsHelp: '碰撞、纜線張力與纏纜、拍照、解鎖與上鎖的震動回饋。不支援的裝置會靜默略過。'
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
