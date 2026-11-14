// Underwater beautification as a fidelity item: shallow sun shafts, caustics and a vignette. A real vehicle
// camera shows none of these, so the item exceeds the real vehicle and is off in the `real` preset.
// `?beautify=1` / `?beautify=0` overrides the preset for one session, like the other per-item URL flags.
import { registerFidelityItem, getFidelity } from '../fidelity.js';

const STRINGS = {
  waterBeautify: '水下畫面美化',
  waterBeautifyHelp: '淺水光束、焦散與暗角。真機影像沒有這些效果。'
};
export const BEAUTIFY_ID = 'waterBeautify';

function beautifyFromUrl(params) {
  if (!params.has('beautify')) return undefined;
  return params.get('beautify') === '1' || params.get('beautify') === 'true';
}
function isOn(value) {
  return value === true;
}

registerFidelityItem({
  id: BEAUTIFY_ID, descriptionKey: 'waterBeautifyHelp', type: 'toggle',
  defaults: { real: false, assisted: true }, exceedsReal: true, exceeds: isOn, urlValue: beautifyFromUrl
}, STRINGS);

// Current value; consumers read it every frame, so preset changes in flight apply immediately.
export function beautifyEnabled() {
  return getFidelity().get(BEAUTIFY_ID) === true;
}
