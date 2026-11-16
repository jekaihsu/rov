// Registers the underwater-audio fidelity item. Real observation-class ROVs have no hydrophone, so
// thruster, impact and underwater ambience exceed the real vehicle and stay off in the `real` preset.
import {registerFidelityItem, getFidelity} from '../fidelity.js';

const STRINGS = {
  underwaterAudio: '水下音效',
  underwaterAudioHelp: '推進器、碰撞與水下環境聲。真機無水聽器，操作員在水面聽不到。'
};
export const UNDERWATER_AUDIO_ID = 'underwaterAudio';

function underwaterFromUrl(params) {
  if (!params.has('underwaterAudio')) return undefined;
  return params.get('underwaterAudio') === '1' || params.get('underwaterAudio') === 'true';
}

function isOn(value) {
  return value === true;
}

registerFidelityItem({
  id: UNDERWATER_AUDIO_ID,
  descriptionKey: 'underwaterAudioHelp',
  type: 'toggle',
  defaults: {real: false, assisted: true},
  exceedsReal: true,
  exceeds: isOn,
  urlValue: underwaterFromUrl
}, STRINGS);

export function underwaterAudioEnabled(fidelity = getFidelity()) {
  return fidelity.get(UNDERWATER_AUDIO_ID) === true;
}
