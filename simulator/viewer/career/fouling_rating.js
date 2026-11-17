// After a hull-fouling photo deliverable with def.rating (0–4 truth) is accepted, prompt the pilot to pick the
// fouling rating. Picks are stored here for the tracker/scoring layer to compare against truth later.

import { localize } from '../i18n/core.js';

const STRINGS = localize('career.fouling_rating', {
  title: '附著評級',
  prompt: '為「{label}」選擇評級',
  fr0: 'FR0 無附著',
  fr1: 'FR1 薄藻膜',
  fr2: 'FR2 零星硬附著',
  fr3: 'FR3 明顯硬附著',
  fr4: 'FR4 厚層／群生',
  close: '關閉',
});

const LABELS = [STRINGS.fr0, STRINGS.fr1, STRINGS.fr2, STRINGS.fr3, STRINGS.fr4];

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function format(template, values) {
  return template.replace(/\{(\w+)\}/g, function fill(match, key) {
    return key in values ? String(values[key]) : match;
  });
}

/** Absolute difference between the pilot pick and scene truth (0–4). */
export function foulingRatingDelta(pick, truth) {
  const a = Number(pick);
  const b = Number(truth);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  return Math.abs(a - b);
}

/** True when the pick matches the truth rating. */
export function foulingRatingOk(pick, truth) {
  return foulingRatingDelta(pick, truth) === 0;
}

/** Short FR0–FR4 label for a rating value. */
export function foulingRatingLabel(value) {
  const n = Math.max(0, Math.min(4, Math.round(Number(value))));
  return Number.isFinite(n) ? LABELS[n] : '';
}

/**
 * onRated(itemId, value): called when the pilot confirms a pick.
 * Returns {prompt, close, lastRating, picks}.
 */
export function installFoulingRating({ onRated } = {}) {
  const picks = new Map();
  const root = element('div', 'fouling-rating');
  root.hidden = true;
  root.setAttribute('role', 'dialog');
  root.setAttribute('aria-modal', 'true');
  const card = element('div', 'fouling-rating-card');
  const title = element('h2', 'fouling-rating-title', STRINGS.title);
  const lead = element('p', 'fouling-rating-lead');
  const list = element('div', 'fouling-rating-options');
  const dismiss = element('button', 'fouling-rating-close', STRINGS.close);
  dismiss.type = 'button';
  card.append(title, lead, list, dismiss);
  root.append(card);
  document.body.append(root);

  let activeId = '';

  function close() {
    activeId = '';
    root.hidden = true;
  }

  function lastRating(itemId) {
    return picks.has(itemId) ? picks.get(itemId) : null;
  }

  function choose(value) {
    if (!activeId) return;
    const n = Math.max(0, Math.min(4, Math.round(Number(value))));
    picks.set(activeId, n);
    const id = activeId;
    close();
    onRated?.(id, n);
  }

  function prompt(itemId, label) {
    activeId = String(itemId || '');
    if (!activeId) return;
    lead.textContent = format(STRINGS.prompt, { label: label || activeId });
    list.replaceChildren();
    for (let i = 0; i <= 4; i += 1) {
      const button = element('button', 'fouling-rating-option', LABELS[i]);
      button.type = 'button';
      button.dataset.rating = String(i);
      button.addEventListener('click', function onPick() {
        choose(i);
      });
      list.append(button);
    }
    root.hidden = false;
  }

  dismiss.addEventListener('click', close);

  return { prompt, close, lastRating, picks };
}
