// In-flight objective card: makes the first-dive checklist and expedition contracts reachable without opening
// the engineering drawer (both stay in the drawer too). For a player's first dives it mirrors the pilot guide's
// four steps (pilot_guide.js owns the checks; this card only reads its list), and in the expedition sea it shows
// the active contract's steps or the contracts on offer with an accept button. Collapsible; never shown during a
// chapter (the story radio teaches the same steps) or a replay. During a YX work order (career/dive.js) the card
// shows the order's deliverable checklist instead.
import { acceptContract, cancelContract, contractBoard } from './contracts.js';
import { recordLine } from '../menu/cards.js';
import { recordFor } from './results_model.js';

const STRINGS = {
  guide: '首次潛航練習',
  guideDone: '基本操作完成，開始探索吧！',
  hideGuide: '不再顯示練習',
  contracts: '工程委託',
  accept: '接取',
  cancel: '取消委託',
  active: '進行中',
  collapse: '收合',
  expand: '展開',
  meters: '{d} m',
};
export const CARD_KEY = 'rov.objectiveCard.v1';
// The checklist is offered on the first few dives and until the player hides it.
export const GUIDE_DIVES = 3;
const DONE_LINGER_MS = 4000;
const UPDATE_MS = 200;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function readSave() {
  try {
    const save = JSON.parse(localStorage.getItem(CARD_KEY) || '{}');
    return { dives: Number(save.dives) || 0, guideHidden: !!save.guideHidden, collapsed: !!save.collapsed };
  } catch {
    return { dives: 0, guideHidden: false, collapsed: false };
  }
}

function writeSave(save) {
  try {
    localStorage.setItem(CARD_KEY, JSON.stringify(save));
  } catch {
    // Storage may be unavailable; the card simply shows again next time.
  }
}

// Steps of the pilot guide as rendered by pilot_guide.js: [{id, label, done}].
function guideSteps() {
  return [...document.querySelectorAll('#pilotGuide li[data-step]')].map(function step(item) {
    return { id: item.dataset.step, label: item.textContent, done: item.dataset.complete === 'true' };
  });
}

// career: optional career/dive.js runtime; its panel(state) returns {title, count, node} during a work order.
export function installObjectiveCard({ send, getSession, readOnly = false, career = null }) {
  const save = readSave();
  if (!readOnly) {
    save.dives += 1;
    writeSave(save);
  }
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
  const guide = element('div', 'objective-guide');
  const guideHead = element('p', 'objective-subhead');
  const guideList = element('ol', 'objective-steps');
  const hideGuide = element('button', 'objective-link', STRINGS.hideGuide);
  hideGuide.type = 'button';
  guide.append(guideHead, guideList, hideGuide);
  const board = element('div', 'objective-contracts');
  const careerSlot = element('div', 'objective-career');
  const feedback = element('p', 'objective-feedback');
  feedback.setAttribute('role', 'status');
  body.append(careerSlot, guide, board, feedback);
  root.append(head, body);
  document.body.append(root);
  let collapsed = save.collapsed;
  let guideDoneAt = 0;
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
  hideGuide.addEventListener('click', function hide() {
    save.guideHidden = true;
    writeSave(save);
    guide.hidden = true;
  });
  setCollapsed(collapsed);

  function host() {
    const session = getSession();
    return !session || !!session.is_host;
  }
  function renderGuide(steps) {
    const done = steps.filter(function complete(step) {
      return step.done;
    }).length;
    guideList.replaceChildren(...steps.map(function item(step) {
      const line = element('li', '', step.label);
      line.dataset.complete = String(step.done);
      return line;
    }));
    if (done === steps.length && steps.length) {
      guideDoneAt ||= performance.now();
      guideList.replaceChildren(element('li', 'objective-done', STRINGS.guideDone));
    }
    return `${done}/${steps.length}`;
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
    careerSlot.hidden = !work;
    if (work) {
      if (careerSlot.firstChild !== work.node) careerSlot.replaceChildren(work.node);
      guide.hidden = true;
      board.hidden = true;
      root.hidden = false;
      title.textContent = work.title;
      count.textContent = work.count;
      return;
    }
    const inChapter = ['active', 'completed'].includes(state.campaign?.status);
    const data = inChapter ? null : contractBoard(state, host());
    const steps = guideSteps();
    const lingering = !guideDoneAt || now - guideDoneAt < DONE_LINGER_MS;
    const showGuide = !inChapter && !save.guideHidden && save.dives <= GUIDE_DIVES && steps.length > 0 && lingering;
    guide.hidden = !showGuide;
    board.hidden = !data;
    root.hidden = !showGuide && !data;
    if (root.hidden) return;
    const progress = showGuide ? renderGuide(steps) : '';
    if (data) renderBoard(data);
    title.textContent = data ? STRINGS.contracts : STRINGS.guide;
    guideHead.textContent = `${STRINGS.guide} ${progress}`;
    guideHead.hidden = !data;
    if (data?.active) count.textContent = STRINGS.active;
    else count.textContent = data ? '' : progress;
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
