// Settings rows for the new-player hints (play/onboarding.js), shared by the launch menu's and the pause menu's
// 介面 tab: an on/off toggle in the mountToggles item shape and a 重新顯示新手提示 button that starts them over.
import { ONBOARDING_CHANGED, loadProgress, resetProgress, saveProgress } from './onboarding_model.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('play.onboarding_settings', {
  toggle: ['新手提示', '飛行中在畫面左側提示下一個基本操作；第一次遇到纜線張力、DVL 或低能見度時說明怎麼處理。'],
  reset: '重新顯示新手提示',
  resetDone: '新手提示已重設，會從第一步開始提示。',
});

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function announce() {
  document.dispatchEvent(new CustomEvent(ONBOARDING_CHANGED));
}

// idPrefix names the controls (menu → #menuOnboarding, #menuOnboardingReset). Returns {toggle, reset}: toggle is a
// mountToggles item, reset an element holding the button and its confirmation line.
export function onboardingSettings(idPrefix) {
  const [label, help] = STRINGS.toggle;
  const toggle = {
    id: `${idPrefix}Onboarding`,
    label,
    help,
    checked: loadProgress().enabled,
    onChange(value) {
      const progress = loadProgress();
      progress.enabled = value;
      saveProgress(progress);
      announce();
    },
  };
  const button = element('button', 'menu-next menu-wide', STRINGS.reset);
  button.type = 'button';
  button.id = `${idPrefix}OnboardingReset`;
  const note = element('p', 'menu-help');
  note.setAttribute('role', 'status');
  button.addEventListener('click', function resetHints() {
    resetProgress();
    note.textContent = STRINGS.resetDone;
    const box = document.getElementById(toggle.id);
    if (box) box.checked = true;
    announce();
  });
  const reset = element('div', 'menu-field onboarding-settings');
  reset.append(button, note);
  return { toggle, reset };
}
