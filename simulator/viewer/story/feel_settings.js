// Flight feedback switches shared by the menu and the live presentation.
import {UNDERWATER_AUDIO_ID} from '../audio/fidelity.js';
import {getFidelity, registerFidelityItem} from '../fidelity.js';
import {localize} from '../i18n/index.js';

const STRINGS = localize('story.feel_settings', {
  "motorSound": "推進器聲",
  "waterSound": "深度環境聲",
  "contactSound": "水下撞擊聲",
  "strainSound": "纜線拉扯聲",
  "switchSound": "控制台機械聲",
  "contactVideo": "碰撞影像干擾",
  "photoFlash": "拍照閃光",
  "loadReadout": "受力時顯示張力",
  "crewCalls": "船員即時通報",
  "idleCalls": "任務空檔通話",
  "osVoice": "作業系統語音合成",
  "osVoiceHelp": "缺配音片段時用本機語音朗讀無線電字幕。預設關閉。"
});

const underwater = new Set(['motorSound', 'waterSound', 'contactSound', 'strainSound']);
function underwaterOverride(params) {
  if (!params.has('underwaterAudio')) return undefined;
  return ['true', '1'].includes(params.get('underwaterAudio'));
}

for (const id of Object.keys(STRINGS)) {
  if (id.endsWith('Help')) continue;
  if (id === 'osVoice') {
    registerFidelityItem({
      id,
      type: 'toggle',
      descriptionKey: 'osVoiceHelp',
      defaults: {real: false, assisted: false},
      exceedsReal: true,
      presetNeutral: false
    }, STRINGS);
    continue;
  }
  const exceedsReal = underwater.has(id);
  registerFidelityItem({
    id,
    type: 'toggle',
    defaults: {real: !exceedsReal, assisted: true},
    urlValue: exceedsReal ? underwaterOverride : undefined,
    exceedsReal,
    presetNeutral: !exceedsReal
  }, STRINGS);
}

// Preserve the existing master switch and saved master-only mixes. Turning up one channel opens the bus.
export function bindUnderwaterMix(fidelity) {
  function anyChannel() {
    return [...underwater].some(id => fidelity.get(id));
  }
  function restoreMix() {
    if (fidelity.get(UNDERWATER_AUDIO_ID) && !anyChannel()) {
      for (const id of underwater) fidelity.set(id, true);
    }
  }
  restoreMix();
  return fidelity.subscribe(function change(snapshot, changed) {
    if (changed.length !== 1) return;
    const [id] = changed;
    if (id === UNDERWATER_AUDIO_ID) restoreMix();
    if (underwater.has(id) && (snapshot.values[id] || !anyChannel())) {
      fidelity.set(UNDERWATER_AUDIO_ID, snapshot.values[id]);
    }
  });
}
bindUnderwaterMix(getFidelity());
