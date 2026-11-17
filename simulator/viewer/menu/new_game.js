// Full-screen difficulty picker shown once for a fresh player (and reopenable from settings).
// Left: 簡單／標準／真實 as large vertical options; right: live stage preview pose for that preset;
// bottom: two–three lines of difference plus the licence-hours note. Only the confirm control uses safety orange.
// Layout follows docs/design/big-picture/: full-bleed scene, one heavy title, thick ice selection frame, no cards.
import {DIFFICULTY_ORDER, getFidelity, fidelityText} from '../fidelity.js';
import {localize} from '../i18n/index.js';

const STRINGS = localize('menu.new_game', {
  title: '選擇難度',
  confirm: '確認',
  hours: '考照與真實時數只計算真實模式。',
  navigate: '移動',
  reopen: '難度選擇',
  reopenHelp: '重新開啟開場的難度畫面。',
  options: {
    assisted: {
      label: '簡單',
      blurb: '第三人稱與定點輔助、無影像延遲。潛前檢查由船員代做。適合先熟悉手感。',
    },
    standard: {
      label: '標準',
      blurb: '機載視角與影像延遲；定深輔助開、定點關。完整潛前檢查。介於簡單與真實之間。',
    },
    real: {
      label: '真實',
      blurb: '與真機一致：機載、有延遲、無超出真機的輔助。完整潛前檢查。硬核擬真預設。',
    },
  },
});

export const DIFFICULTY_CHOSEN_KEY = 'rov.difficulty.chosen.v1';
// Same jacket site / vehicle as the title backdrop; poses bias the vehicle into the right half.
const PREVIEW_POSES = {
  assisted: 'new_game_assisted',
  standard: 'new_game_standard',
  real: 'new_game_real',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function readStore(storage) {
  try {
    return storage?.getItem(DIFFICULTY_CHOSEN_KEY) || '';
  } catch {
    return '';
  }
}

function writeStore(storage, value) {
  try {
    storage?.setItem(DIFFICULTY_CHOSEN_KEY, value);
  } catch {
    // Private browsing: the session still applies the preset without persistence.
  }
}

export function hasDifficultyChosen(storage = globalThis.localStorage) {
  return readStore(storage) === '1';
}

export function rememberDifficultyChosen(storage = globalThis.localStorage) {
  writeStore(storage, '1');
}

export function difficultyLabel(name) {
  return STRINGS.options[name]?.label || fidelityText(
    {real: 'presetReal', standard: 'presetStandard', assisted: 'presetAssisted'}[name]
  ) || name;
}

// Builds the screen. onConfirm(preset) runs after the preset is written; ctx.stage drives the live preview.
export function buildNewGame(ctx) {
  const fidelity = getFidelity();
  const root = element('section', 'menu-screen new-game');
  root.dataset.screen = 'new_game';
  root.setAttribute('aria-label', STRINGS.title);

  const layout = element('div', 'new-game-layout');
  const list = element('div', 'new-game-options');
  list.setAttribute('role', 'listbox');
  list.setAttribute('aria-label', STRINGS.title);

  const preview = element('div', 'new-game-preview');
  preview.setAttribute('aria-hidden', 'true');
  const previewFrame = element('div', 'new-game-preview-frame');
  const previewLabel = element('p', 'new-game-preview-label');
  previewFrame.append(previewLabel);
  preview.append(previewFrame);

  const foot = element('div', 'new-game-foot');
  const blurb = element('p', 'new-game-blurb');
  const hours = element('p', 'new-game-hours', STRINGS.hours);
  const confirm = element('button', 'new-game-confirm bp-primary', STRINGS.confirm);
  confirm.type = 'button';
  confirm.id = 'newGameConfirm';
  foot.append(blurb, hours, confirm);

  const buttons = {};
  let selected = DIFFICULTY_ORDER.includes(fidelity.preset) ? fidelity.preset : 'real';
  // Accept on an already-highlighted option commits (hand/keyboard); the first paint only previews.
  let allowOptionCommit = false;

  function select(name, {arm = true} = {}) {
    if (!DIFFICULTY_ORDER.includes(name)) return;
    selected = name;
    for (const [key, button] of Object.entries(buttons)) {
      const on = key === name;
      button.setAttribute('aria-selected', String(on));
      button.classList.toggle('is-selected', on);
      if (on) button.dataset.autofocus = '';
      else delete button.dataset.autofocus;
    }
    const option = STRINGS.options[name];
    blurb.textContent = option.blurb;
    previewLabel.textContent = option.label;
    preview.dataset.preset = name;
    root.dataset.difficulty = name;
    ctx.stage?.setPose(PREVIEW_POSES[name] || 'new_game_real');
    if (arm) allowOptionCommit = true;
  }

  function commit() {
    fidelity.setPreset(selected);
    rememberDifficultyChosen();
    ctx.onDifficultyChosen?.(selected);
  }

  for (const name of DIFFICULTY_ORDER) {
    const button = element('button', 'new-game-option');
    button.type = 'button';
    button.dataset.difficulty = name;
    button.id = `newGame-${name}`;
    button.setAttribute('role', 'option');
    button.append(element('span', 'new-game-option-label', STRINGS.options[name].label));
    button.addEventListener('click', function choose() {
      if (allowOptionCommit && selected === name && button.getAttribute('aria-selected') === 'true') {
        commit();
        return;
      }
      select(name);
    });
    buttons[name] = button;
    list.append(button);
  }

  confirm.addEventListener('click', function accept() {
    commit();
  });

  layout.append(list, preview);
  root.append(element('h1', 'new-game-title', STRINGS.title), layout, foot);

  function enter() {
    const current = DIFFICULTY_ORDER.includes(fidelity.preset) ? fidelity.preset : 'real';
    allowOptionCommit = false;
    select(current, {arm: false});
  }

  return {
    element: root,
    pose: 'new_game_real',
    enter,
    prompts: [['navigate', STRINGS.navigate], ['accept', STRINGS.confirm]],
    select,
    get selected() {
      return selected;
    },
  };
}

export {STRINGS as NEW_GAME_STRINGS};
