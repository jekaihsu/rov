// Registers the in-dive music fidelity item. A real pilot hears the control room, not a soundtrack, so music
// while the vehicle is in the water (calm dive bed and incident tension) exceeds the real vehicle and stays off
// in the `real` preset. Menu, briefing and results music is a plain volume preference and is not gated here.
import {registerFidelityItem, getFidelity} from '../fidelity.js';

const STRINGS = {
  diveMusic: '潛航配樂',
  diveMusicHelp: '下潛時播放背景音樂，事故時改為緊張配樂。'
    + '真機操作員聽不到配樂；選單與結算音樂只受音量控制。'
};
export const DIVE_MUSIC_ID = 'diveMusic';

function diveMusicFromUrl(params) {
  if (!params.has('diveMusic')) return undefined;
  return params.get('diveMusic') === '1' || params.get('diveMusic') === 'true';
}

function isOn(value) {
  return value === true;
}

registerFidelityItem({
  id: DIVE_MUSIC_ID,
  descriptionKey: 'diveMusicHelp',
  type: 'toggle',
  defaults: {real: false, assisted: true},
  exceedsReal: true,
  exceeds: isOn,
  urlValue: diveMusicFromUrl
}, STRINGS);

export function diveMusicEnabled(fidelity = getFidelity()) {
  return fidelity.get(DIVE_MUSIC_ID) === true;
}
