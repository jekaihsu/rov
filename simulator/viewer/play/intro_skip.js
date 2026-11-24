// Skipping the launch cinematic: the #skipIntro control shows a small glyph-aware prompt ("hold ○ to skip · Esc").
// A pad skips it by holding the menu `back` button (input/bindings.js) for HOLD_MS; Esc and a click skip at once.
// The pad hold goes through the input layer: while the cinematic can be skipped the `back` action is enabled, so
// the menu context owns that button and its flight action (record) never fires underneath the prompt.
import { HOLD_MS } from '../input/bindings.js';
import { deviceFamily, actionGlyph } from '../input/glyphs.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('play.intro_skip', {
  label: '跳過下水動畫',
  hold: '按住跳過',
});
const BUTTON_ID = 'skipIntro';
// Another cutscene that borrows the prompt (story/cold_open.js) names itself here; null restores the label.
let labelOverride = null;
let rerender = null;

export function setIntroSkipLabel(text) {
  labelOverride = text || null;
  rerender?.();
}

// True while the cinematic plays and can be skipped (not while it waits on deck for the pre-dive procedure).
export function introSkippable() {
  const button = globalThis.document?.getElementById(BUTTON_ID);
  return !!button && !button.hidden;
}

function span(className, html) {
  const node = document.createElement('span');
  node.className = className;
  node.innerHTML = html;
  return node;
}

// input: the object installInput returned. button: the #skipIntro element. skip(): skip the cinematic.
// active(): whether a cinematic is running at all (held on deck included); Esc is consumed then, as before.
export function installIntroSkip({ input, button, skip, active }) {
  if (!button) return { refresh() {} };
  let family = '';
  let heldMs = 0;
  function render() {
    const label = labelOverride || STRINGS.label;
    const parts = [];
    if (family) parts.push(span('skip-cap', actionGlyph('back', input.keyRows(), family)), span('skip-text', STRINGS.hold));
    parts.push(span('skip-cap', actionGlyph('back', input.keyRows(), 'keyboard')));
    if (!family) parts.push(span('skip-text', label));
    button.replaceChildren(...parts);
    button.setAttribute('aria-label', label);
    button.dataset.family = family || 'keyboard';
  }
  // How the last skip came in (pad, key or click), for the browser checks.
  function skipBy(source) {
    if (introSkippable()) button.dataset.skipped = source;
    skip();
  }
  function setProgress(value) {
    button.style.setProperty('--skip-hold', String(value));
    button.classList.toggle('holding', value > 0);
  }
  // Called every pad frame while the prompt is up (continuous action); a key press arrives with dt 0 instead and is
  // handled by the keydown listener below.
  function hold(value, dt) {
    if (!dt) return;
    heldMs = value > 0.5 ? heldMs + dt * 1000 : 0;
    setProgress(Math.min(1, heldMs / HOLD_MS));
    if (heldMs < HOLD_MS) return;
    heldMs = 0;
    setProgress(0);
    skipBy('pad');
  }
  input?.registerActions?.({ back: { continuous: true, enabled: introSkippable, run: hold } });
  new MutationObserver(function visibility() {
    heldMs = 0;
    setProgress(0);
  }).observe(button, { attributes: true, attributeFilter: ['hidden'] });
  document.addEventListener('rov-input-device', function deviceChanged(event) {
    const detail = event.detail;
    const next = detail && detail !== 'touch' ? deviceFamily(detail) : '';
    if (next === family) return;
    family = next;
    render();
  });
  document.addEventListener('rov-key-rows', render);
  button.addEventListener('click', function clicked() {
    skipBy('click');
  });
  addEventListener('keydown', function escape(event) {
    if (!active() || !input.keyRows().find(row => row.action === 'back')?.keys?.includes(event.code)) return;
    event.preventDefault();
    skipBy('key');
  });
  render();
  rerender = render;
  return { refresh: render };
}
