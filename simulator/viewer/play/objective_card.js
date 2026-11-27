// In-flight objective card: expedition contracts (and YX work-order checklists) without opening the engineering
// drawer. The first-dive practice list lives only in play/onboarding.js (and the drawer pilot guide); this card
// no longer mirrors it, so the player never sees two checklists at once. Collapsible; never shown during a
// chapter or a replay. During a YX work order (career/dive.js) the card shows the order's deliverable checklist.
import { acceptContract, cancelContract, contractBoard } from './contracts.js';
import { recordLine } from '../menu/cards.js';
import { recordFor } from './results_model.js';
import { localize } from '../i18n/index.js';
import { objectiveCardStore } from '../saves/registry.js';

const STRINGS = localize('play.objective_card', {
  contracts: '工程委託',
  accept: '接取',
  cancel: '取消委託',
  active: '進行中',
  collapse: '收合',
  expand: '展開',
  meters: '{d} m',
});

export const CARD_KEY = 'rov.objectiveCard.v1';
const UPDATE_MS = 200;

// Which body sections the card mounts. Never includes a first-dive guide — that list lives in onboarding.
export function objectiveCardSections({ careerWork = false, inChapter = false, hasBoard = false } = {}) {
  if (careerWork) return ['career'];
  if (inChapter) return [];
  if (hasBoard) return ['contracts'];
  return [];
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function readSave() {
  const { value } = objectiveCardStore.load();
  return { collapsed: !!value.collapsed };
}

function writeSave(save) {
  objectiveCardStore.save(save);
}

// career: optional career/dive.js runtime; its panel(state) returns {title, count, node} during a work order.
export function installObjectiveCard({ send, getSession, readOnly = false, career = null }) {
  const save = readSave();
  const root = element('section', 'objective-card');
  root.id = 'objectiveCard';
  root.hidden = true;
  const head = element('button', 'objective-head');
  head.type = 'button';
  head.id = 'objectiveToggle';
  const title = element('span', 'objective-title');
  const count = element('span', 'objective-count');
  head.append(title, count);
  const body = element('div', 'objective-body');
  const board = element('div', 'objective-contracts');
  const careerSlot = element('div', 'objective-career');
  const feedback = element('p', 'objective-feedback');
  feedback.setAttribute('role', 'status');
  body.append(careerSlot, board, feedback);
  root.append(head, body);
  document.body.append(root);
  let collapsed = save.collapsed;
  let boardSignature = '';
  let last = 0;

  function setCollapsed(value) {
    collapsed = value;
    save.collapsed = value;
    writeSave(save);
    body.hidden = collapsed;
    head.setAttribute('aria-expanded', String(!collapsed));
    head.title = collapsed ? STRINGS.expand : STRINGS.collapse;
  }
  head.addEventListener('click', function toggle() {
    setCollapsed(!collapsed);
  });
  setCollapsed(collapsed);

  function host() {
    const session = getSession();
    return !session || !!session.is_host;
  }
  function renderBoard(data) {
    const signature = JSON.stringify(data);
    if (signature === boardSignature) return;
    boardSignature = signature;
    board.replaceChildren();
    if (data.active) {
      board.append(element('p', 'objective-active', `${STRINGS.active} · ${data.active.label}`));
      const steps = element('ol', 'objective-steps');
      for (const step of data.active.steps) {
        const text = step.distance == null ? step.label
          : `${step.label} · ${STRINGS.meters.replace('{d}', step.distance.toFixed(1))}`;
        const line = element('li', '', text);
        line.dataset.complete = String(step.done);
        if (!step.done && step.progress != null) {
          const bar = element('progress');
          bar.max = 1;
          bar.value = step.progress;
          line.append(bar);
        }
        steps.append(line);
      }
      const cancel = element('button', 'objective-link', STRINGS.cancel);
      cancel.type = 'button';
      cancel.disabled = !data.host;
      cancel.addEventListener('click', function cancelActive() {
        feedback.textContent = cancelContract(send);
      });
      board.append(steps, cancel);
      return;
    }
    for (const offer of data.offers) {
      const row = element('div', 'objective-offer');
      const text = element('span', 'objective-offer-text');
      text.append(element('strong', '', offer.label), element('small', '', offer.reason || offer.help));
      const record = recordFor(`contract:${offer.kind}`);
      const best = element('small', 'objective-record', recordLine(record));
      best.dataset.medal = record?.medal || 'none';
      text.append(best);
      const accept = element('button', 'objective-accept', STRINGS.accept);
      accept.type = 'button';
      accept.dataset.contract = offer.kind;
      accept.disabled = !offer.enabled;
      accept.addEventListener('click', function acceptOffer() {
        feedback.textContent = acceptContract(send, offer.kind);
      });
      row.append(text, accept);
      board.append(row);
    }
  }
  function update(state) {
    if (readOnly || !state) return;
    const now = performance.now();
    if (now - last < UPDATE_MS) return;
    last = now;
    const work = career?.panel?.(state) || null;
    const inChapter = ['active', 'completed'].includes(state.campaign?.status);
    const data = inChapter || work ? null : contractBoard(state, host());
    const sections = objectiveCardSections({
      careerWork: !!work,
      inChapter,
      hasBoard: !!data,
    });
    careerSlot.hidden = !sections.includes('career');
    board.hidden = !sections.includes('contracts');
    root.hidden = sections.length === 0;
    if (work) {
      if (careerSlot.firstChild !== work.node) careerSlot.replaceChildren(work.node);
      title.textContent = work.title;
      count.textContent = work.count;
      return;
    }
    if (root.hidden) return;
    if (data) renderBoard(data);
    title.textContent = STRINGS.contracts;
    if (data?.active) count.textContent = STRINGS.active;
    else count.textContent = '';
  }
  return {
    update,
    // Opens the card on the contract board (the results screen's 接下一項委託).
    showContracts() {
      setCollapsed(false);
      board.querySelector('button:not(:disabled)')?.focus({ preventScroll: true });
    },
    get visible() {
      return !root.hidden;
    },
  };
}
