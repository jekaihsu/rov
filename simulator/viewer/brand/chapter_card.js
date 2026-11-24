// Chapter title card: a full-screen plate shown for a few seconds when a story chapter (or, later, a contract)
// starts. Left half is the site plate, right half a paper panel with the index line, client, chapter symbol, big
// title and sub line (docs/design/key-art/chapter_card.html is the approved look).
//
// Three layers, so the career work can reuse the lower two:
//   titleCard(data)            → the card element only (no timing); used by the demo page and by callers that
//                                 place a card themselves.
//   showTitleCard(data, opts)  → puts the card over the page for `duration`, dismisses on any key, pointer or
//                                 pad button, and resolves when it is gone. Contracts call this directly.
//   installChapterCards(opts)  → the in-game wiring: watches the campaign state and shows the card when a
//                                 chapter starts. Never during replays. In the `real` preset the card only
//                                 appears while the page is still starting up (before the dive); a chapter
//                                 started mid-dive shows it only when the fidelity item below is on.
import {registerFidelityItem, getFidelity} from '../fidelity.js';
import {STRINGS as CHAPTER_STRINGS, chapterCardData, plateFor} from './chapters.js';
import {chapterSymbol, svgNode, yxMark} from './marks.js';
import { localize } from '../i18n/index.js';

export const CARD_DURATION_MS = 3500;
export const CARD_FADE_MS = 400;
// How long after the first campaign state a chapter start still counts as "before the dive".
export const BOOT_WINDOW_MS = 20000;
export const IN_DIVE_ITEM = 'chapterCardInDive';
const SYMBOL_SIZE = 420;

const STRINGS = localize('brand.chapter_card', {
  chapterCardInDive: '潛航中顯示章節標題卡',
  chapterCardInDiveHelp: '真實作業中畫面不會被標題卡蓋住；關閉時標題卡只在下水前出現。'
    + '開啟後，潛航中切換章節也會顯示。',
});

registerFidelityItem({
  id: IN_DIVE_ITEM,
  labelKey: IN_DIVE_ITEM,
  descriptionKey: 'chapterCardInDiveHelp',
  type: 'toggle',
  defaults: {real: false, assisted: true},
  exceedsReal: true,
}, STRINGS);

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function plateSources(data) {
  if (data.image) return [data.image];
  if (!data.scenario) return [];
  return [
    new URL(`plates/${plateFor(data.scenario)}.jpg`, import.meta.url).href,
    new URL(`../menu/previews/${data.scenario}.jpg`, import.meta.url).href,
  ];
}

// The photo half. When no plate loads, the half stays a navy drawing of the chapter symbol.
function photoHalf(data) {
  const half = element('div', 'brand-card-photo');
  const drawing = element('div', 'brand-card-drawing');
  drawing.append(svgNode(chapterSymbol(data.symbol, {size: SYMBOL_SIZE})));
  half.append(drawing);
  const sources = plateSources(data);
  if (!sources.length) return half;
  const image = element('img');
  image.alt = '';
  image.decoding = 'async';
  let index = 0;
  image.addEventListener('load', function plateLoaded() {
    half.dataset.plate = '';
  });
  image.addEventListener('error', function nextPlate() {
    index += 1;
    if (index < sources.length) image.src = sources[index];
    else image.remove();
  });
  image.src = sources[0];
  half.append(image);
  return half;
}

/**
 * The card element. data: {number, client, symbol, title, sub, scenario?, image?}. `symbol` is a chapter symbol
 * name from brand/marks.js; `scenario` picks the site plate, `image` overrides it with any URL.
 */
export function titleCard(data) {
  const card = element('section', 'brand-card');
  card.setAttribute('aria-label', `${CHAPTER_STRINGS.cardLabel}：${data.title}`);
  card.dataset.symbol = data.symbol || 'generic';
  const paper = element('div', 'brand-card-paper brand-paper');
  const head = element('div', 'brand-card-head');
  head.append(element('p', 'brand-card-number brand-caption', data.number));
  head.append(element('p', 'brand-card-client brand-caption', data.client));
  const symbol = element('div', 'brand-card-symbol');
  symbol.append(svgNode(chapterSymbol(data.symbol, {size: SYMBOL_SIZE, rough: true})));
  const foot = element('div', 'brand-card-foot');
  foot.append(element('h2', 'brand-card-title', data.title));
  foot.append(element('p', 'brand-card-sub brand-caption', data.sub));
  const mark = element('div', 'brand-card-mark');
  mark.append(svgNode(yxMark({variant: 'compact'})));
  paper.append(head, symbol, foot, mark);
  card.append(photoHalf(data), paper);
  return card;
}

// Pad input reaches the card through the input layer, which announces a pad on `rov-input-device` whenever its
// buttons or sticks change. A pad's first announcement is only its resting state, so it is not a press.
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

/**
 * Show a card over the page. Options: duration (ms, default 3.5 s), parent. Returns {element, dismiss, done}:
 * `done` resolves once the card has left, with what ended it ('timeout', 'key', 'pointer', 'pad' or the string
 * given to dismiss()). The first key press, pointer press or pad button dismisses it; the key press is consumed
 * so it does not also act on the game underneath. Input is never held past `duration`.
 */
export function showTitleCard(data, {duration = CARD_DURATION_MS, parent = document.body} = {}) {
  const overlay = element('div', 'brand-card-overlay');
  overlay.dataset.card = data.id || data.symbol || '';
  overlay.append(titleCard(data), element('p', 'brand-card-skip brand-caption', CHAPTER_STRINGS.skip));
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
    setTimeout(remove, CARD_FADE_MS);
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
  return {element: overlay, dismiss, done};
}

/**
 * Whether a chapter start should show its card. Pure, for tests.
 * replay: read-only playback. bootOpen: the page is still starting up (before the dive). inDive: the fidelity
 * item that allows the card over the camera view mid-dive (off in `real`).
 */
export function shouldShowChapterCard({replay, bootOpen, inDive}) {
  if (replay) return false;
  return !!bootOpen || !!inDive;
}

/**
 * In-game wiring. Call update(state) with every server state. Options: readOnly (replay), fidelity, now, show.
 * Exposes window.__brandCard = {shown, last, dismissed, visibleMs} for the browser check.
 */
export function installChapterCards({
  readOnly = false,
  fidelity = getFidelity(),
  now = function clock() {
    return performance.now();
  },
  show = showTitleCard,
} = {}) {
  let firstStateAt = null;
  let bootUsed = false;
  let activeKey = '';
  const report = {shown: 0, last: '', dismissed: '', visibleMs: 0};
  if (typeof window !== 'undefined') window.__brandCard = report;
  function bootOpen() {
    return !bootUsed && firstStateAt !== null && now() - firstStateAt <= BOOT_WINDOW_MS;
  }
  function update(state) {
    const campaign = state?.campaign;
    if (readOnly || !campaign) return;
    if (firstStateAt === null) firstStateAt = now();
    const key = campaign.status === 'active' && campaign.chapter ? campaign.chapter : '';
    if (key === activeKey) return;
    activeKey = key;
    if (!key) return;
    const chapter = campaign.chapters?.find(function byId(entry) {
      return entry.id === key;
    }) || {id: key, title: key};
    // The prelude (cold open) opens on black and ends on its own card (story/cold_open.js).
    if (campaign.directed || chapter.category === 'prelude') return;
    const allowed = shouldShowChapterCard({
      replay: readOnly,
      bootOpen: bootOpen(),
      inDive: fidelity.get(IN_DIVE_ITEM) === true,
    });
    bootUsed = true;
    if (!allowed) return;

    report.shown += 1;
    report.last = key;
    report.dismissed = '';
    const shownAt = now();
    show(chapterCardData(chapter))?.done?.then(function cardGone(reason) {
      report.dismissed = reason;
      report.visibleMs = now() - shownAt;
    });
  }
  return {update};
}
