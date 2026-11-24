// Player-side preferences shared by the settings pages, stick sampler and radio overlays.
import { registerFidelityItem, getFidelity } from '../fidelity.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('prefs.accessibility', {
  "leftDeadzone": "左搖桿死區",
  "rightDeadzone": "右搖桿死區",
  "leftResponse": "左搖桿反應曲線",
  "rightResponse": "右搖桿反應曲線",
  "leftInvert": "左搖桿 Y 軸反轉",
  "rightInvert": "右搖桿 Y 軸反轉",
  "subtitleSize": "字幕字級",
  "small": "小",
  "medium": "中",
  "large": "大",
  "extraLarge": "特大",
  "subtitleOpacity": "字幕背景不透明度",
  "speakerColor": "說話者名稱顏色",
  "cyan": "青色",
  "white": "白色",
  "amber": "琥珀色",
  "radioDuration": "無線電字幕停留時間（倍數）",
  "reduceFlashes": "減少拍照與撞擊閃光"
});

function register(id, value, spec) {
  registerFidelityItem({id, defaults: {real: value, assisted: value}, presetNeutral: true, ...spec}, STRINGS);
}

function range(id, value, min, max, step) {
  register(id, value, {type: 'range', min, max, step});
}

function choice(id, initial, values) {
  const options = values.map(value => ({value, labelKey: value}));
  register(id, initial, {type: 'choice', options});
}

for (const side of ['left', 'right']) {
  range(side + 'Deadzone', 0.08, 0, 0.5, 0.01);
  range(side + 'Response', 0, 0, 1, 0.01);
  register(side + 'Invert', false, {type: 'toggle'});
}
choice('subtitleSize', 'medium', ['small', 'medium', 'large', 'extraLarge']);
choice('speakerColor', 'cyan', ['cyan', 'white', 'amber']);
range('subtitleOpacity', 0.72, 0, 1, 0.05);
range('radioDuration', 1, 0.5, 3, 0.25);
register('reduceFlashes', false, {type: 'toggle'});

function applyPresentation() {
  const root = globalThis.document?.documentElement;
  if (!root) return;
  const prefs = getFidelity();
  const sizes = {small: 14, medium: 17, large: 22, extraLarge: 28};
  const colours = {cyan: '#4fd1e0', white: '#fff', amber: '#ffd173'};
  root.style.setProperty('--subtitle-size', sizes[prefs.get('subtitleSize')] + 'px');
  root.style.setProperty('--speaker-color', colours[prefs.get('speakerColor')]);
  root.style.setProperty('--subtitle-opacity', prefs.get('subtitleOpacity'));
  root.classList.toggle('reduce-flashes', prefs.get('reduceFlashes'));
}
getFidelity().subscribe(applyPresentation);
applyPresentation();
