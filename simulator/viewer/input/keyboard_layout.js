// Which keyboard layout is active and the player's own key choices, shared by the input layer, the HUD help card,
// the story radio key caps and the settings tables. The layout is the `keyboardLayout` fidelity item: a pure
// preference (presetNeutral) that defaults to the real controller's stick mapping in `real` and to the PC game
// layout (WASD, Space/C up/down, Q/E turn) in `assisted`, which is also the Steam edition default. Rebound keys
// live in rov.input.v1 under `keys[layout]` (input/settings.js); bindings.js validates that they stay unique.
import {registerFidelityItem, getFidelity} from '../fidelity.js';
import {BINDINGS, KEYBOARD_LAYOUTS, keyboardRows} from './bindings.js';

export const KEYBOARD_LAYOUT_ITEM = 'keyboardLayout';

registerFidelityItem({
  id: KEYBOARD_LAYOUT_ITEM,
  labelKey: KEYBOARD_LAYOUT_ITEM,
  descriptionKey: 'keyboardLayoutHelp',
  type: 'choice',
  options: [{value: 'console', labelKey: 'keyboardConsole'}, {value: 'game', labelKey: 'keyboardGame'}],
  defaults: {real: 'console', assisted: 'game'},
  presetNeutral: true,
}, {
  keyboardLayout: '鍵盤配置',
  keyboardLayoutHelp: '遙控器配置：按鍵代替遙控器搖桿，意義隨控制配置改變（與真機相同）。' +
    '遊戲鍵位：W/S 前後、A/D 平移、Space/C 升降、Q/E 轉向、T 解鎖。按鍵可在手把與鍵盤設定中重新指定。',
  keyboardConsole: '遙控器配置',
  keyboardGame: '遊戲鍵位（WASD）',
});

let published = BINDINGS;
let publishedMode = 'ROV_USA';

export function keyboardLayout(fidelity = getFidelity()) {
  const value = fidelity.get(KEYBOARD_LAYOUT_ITEM);
  return KEYBOARD_LAYOUTS.includes(value) ? value : 'console';
}

// The binding rows for the stored settings (rov.input.v1) and the active layout.
export function rowsFor(settings, fidelity = getFidelity()) {
  const layout = keyboardLayout(fidelity);
  return keyboardRows(layout, settings?.keys?.[layout]);
}

// The input layer publishes the rows it uses so text-only surfaces (pilot guide, story radio) show the same keys.
export function publishKeyRows(rows, operationMode = publishedMode) {
  if (rows === published && operationMode === publishedMode) return;
  published = rows;
  publishedMode = operationMode;
  globalThis.document?.dispatchEvent(new CustomEvent('rov-key-rows', {detail: {rows, operationMode}}));
}

export function currentKeyRows() {
  return published;
}

export function currentOperationMode() {
  return publishedMode;
}
