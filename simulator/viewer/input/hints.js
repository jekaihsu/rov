// Render on-screen key hints from the binding table so displayed keys cannot drift from the real ones.
// actionControlLabels / formatActionHint also feed the HUD unlock line and other single-action captions.
import { actionKey, bindingRow, hintItems, padLabel } from './bindings.js';
import { faceLabels, padNames } from './glyphs.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('input.hints', {
  separator: ' · ', pad: '手把 ', positions: ['下方按鍵', '右側按鍵', '左側按鍵', '上方按鍵'],
});

// Face captions for the pad side of a hint: the active family, or Xbox letters when only a keyboard is in use.
function facesFor(family) {
  if (family === 'generic') return STRINGS.positions;
  if (family && family !== 'keyboard') {
    return padNames(family) || faceLabels(family);
  }
  return faceLabels('xbox');
}

// Key and pad captions for one action on the current device (bound key + face / shoulder label).
export function actionControlLabels(action, { family = 'keyboard', rows, bindings } = {}) {
  const key = actionKey(action, rows) || '';
  const source = bindings && action in bindings ? bindings[action] : bindingRow(action)?.pad;
  const pad = source ? padLabel(source, facesFor(family)) : '';
  return { key, pad };
}

// Fill {key} / {pad} in a locale template; empty parts leave neighbouring punctuation for the caller to avoid.
export function formatActionHint(template, parts) {
  return String(template || '')
    .replaceAll('{key}', parts.key || '')
    .replaceAll('{pad}', parts.pad || '');
}

// Fill an element with <kbd> captions for every key and pad source of the listed contexts.
export function renderKeyHints(element, options = {}) {
  if (!element) return;
  element.replaceChildren();
  const items = hintItems({ axes: true, ...options });
  items.forEach(function appendItem(item, index) {
    if (index) element.append(STRINGS.separator);
    for (const key of item.keys) {
      const cap = document.createElement('kbd');
      cap.textContent = key;
      element.append(cap);
    }
    const pad = item.pad ? `${item.keys.length ? ' / ' : ''}${STRINGS.pad}${item.pad}` : '';
    const note = item.note ? `（${item.note}）` : '';
    element.append(`${pad} ${item.label}${note}`);
  });
}
