// Full-screen licence award: shows licenceCard when a career exam grants a grade (prologue → 見習駕駛員).
// Dismiss on key / pointer / pad, same pattern as chapter_card.js. Pure helpers stay DOM-free for tests.
import {localize} from '../i18n/index.js';
import {licenceCard, licenceModel} from './licence_card.js';

export const AWARD_DURATION_MS = 8000;
export const AWARD_FADE_MS = 400;

const STRINGS = localize('brand.licence_award', {
  skip: '按任意鍵繼續',
  holder: 'R-1',
  overlayLabel: '執照頒發',
});

const padsSeen = new Set();
let padListener = null;

function onInputDevice(event) {
  const id = event.detail;
  if (!id || id === 'touch') return;
  if (!padsSeen.has(id)) {
    padsSeen.add(id);
    return;
  }
  padListener?.();
}

if (typeof document !== 'undefined') document.addEventListener('rov-input-device', onInputDevice);

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

/** Serial from a career save id / createdAt; stable for the same save. */
export function licenceSerial(save) {
  const seed = String(save?.createdAt || save?.updatedAt || 'yx');
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = ((hash << 5) - hash) + seed.charCodeAt(i) | 0;
  const n = Math.abs(hash) % 100000;
  return `YX-PL-${String(n).padStart(5, '0')}`;
}

/**
 * Props for licenceCard from a career settle summary + save.
 * Returns null when the exam did not newly grant a grade.
 */
export function awardProps(summary, save = {}) {
  const before = summary?.licence?.before;
  const after = summary?.licence?.after;
  if (!summary?.exam?.passed || !after || after === 'none' || after === before) return null;
  const hours = summary.hours || {};
  return {
    grade: after,
    holderName: STRINGS.holder,
    issuedOn: save.updatedAt || new Date().toISOString(),
    hoursReal: (hours.total_real_s || 0) / 3600,
    hoursAssisted: (hours.total_assisted_s || 0) / 3600,
    serial: licenceSerial(save),
  };
}

/**
 * Show the award overlay. Returns {element, dismiss, done, model} or null when props are empty.
 */
export function showLicenceAward(props, {duration = AWARD_DURATION_MS, parent = document.body} = {}) {
  if (!props?.grade) return null;
  const model = licenceModel(props);
  const overlay = element('div', 'brand-licence-award');
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', `${STRINGS.overlayLabel}：${model.title}`);
  const stage = element('div', 'brand-licence-stage brand-licence-award-stage');
  stage.append(licenceCard(props));
  overlay.append(stage, element('p', 'brand-caption brand-licence-award-skip', STRINGS.skip));

  let leaving = false;
  let finish;
  const done = new Promise(function whenGone(resolve) {
    finish = resolve;
  });
  let reason = '';

  function remove() {
    overlay.remove();
    finish(reason);
  }

  function dismiss(why) {
    if (leaving) return;
    leaving = true;
    reason = typeof why === 'string' ? why : 'pointer';
    clearTimeout(timer);
    if (padListener === onPad) padListener = null;
    removeEventListener('keydown', onKey, true);
    removeEventListener('pointerdown', onPointer, true);
    overlay.classList.add('leaving');
    setTimeout(remove, AWARD_FADE_MS);
  }

  function onKey(event) {
    if (event.repeat) return;
    event.stopImmediatePropagation();
    event.preventDefault();
    dismiss('key');
  }

  function onPointer() {
    dismiss('pointer');
  }

  function onPad() {
    dismiss('pad');
  }

  function onTimeout() {
    dismiss('timeout');
  }

  addEventListener('keydown', onKey, true);
  addEventListener('pointerdown', onPointer, true);
  padListener = onPad;
  const timer = setTimeout(onTimeout, duration);
  parent.append(overlay);
  if (typeof window !== 'undefined') {
    window.__licenceAward = {shown: true, grade: model.grade, serial: model.serial};
  }
  return {element: overlay, dismiss, done, model};
}

/** Show the award when a settle summary newly grants a licence grade. */
export function awardLicenceFromSummary(summary, save, opts) {
  const props = awardProps(summary, save);
  if (!props) return null;
  return showLicenceAward(props, opts);
}
