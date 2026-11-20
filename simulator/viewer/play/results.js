// End-of-run results screen: when a scenario, co-op inspection, story chapter, incident drill or expedition
// contract ends, the scene stays behind and a big-picture layout (menu/big_picture.js) shows the outcome as one
// large heading, the medal as a thick-outlined tag, one huge number (the payout of a YX work order, else the
// score), one line of record or licence progress, one primary button and text-only secondary actions. The score
// breakdown, the rewards and the pay slip open behind 明細. Gamepad and keys use the menu rows of
// input/bindings.js through the menu navigator. Retry and next chapter send the same commands the drawer
// already sends (reset, mission_mode, campaign_start); nothing here changes physics. Every outcome is also
// announced as a `rov-run-result` event.
import { createMenuNavigator, loadControllerDatabase, renderPrompts } from '../menu/navigator.js';
import {
  DETAILS_LABEL,
  chip,
  createDetailSheet,
  fitTitle,
  linkButton,
  primaryButton,
  stat,
} from '../menu/big_picture.js';
import { createFlightLog } from './flight_log.js';
import { awardLicenceFromSummary } from '../brand/licence_award.js';
import { DELIVERABLES_TITLE, careerHeadline, deliverableLines, renderCareerPanel } from '../career/results_panel.js';
import { loadCareer } from '../career/save.js';
import {
  createOutcomeWatcher,
  formatTime,
  kindLabel,
  medalLabel,
  recordResult,
} from './results_model.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('play.results', {
  success: '任務完成',
  failure: '任務失敗',
  contractDone: '委託完成',
  score: '得分',
  best: '最佳紀錄 {best}',
  newBest: '新紀錄',
  firstBest: '首次完成，已記下成績',
  breakdown: '評分明細',
  rewards: '本次獲得',
  noRewards: '這次沒有新的獎勵。',
  retry: '重來',
  retryChapter: '重玩本章',
  nextChapter: '下一章：{title}',
  storyDone: '已完成目前所有章節',
  moreScenarios: '其他場景訓練',
  moreDrills: '其他事故演練',
  nextContract: '下一項委託',
  nextWorkOrder: '下一張',
  retryWorkOrder: '重來',
  career: '報酬與執照',
  keepExploring: '繼續探索',
  debrief: '講評回放',
  menu: '主選單',
  close: '留在水下',
  hostOnly: '只有房主可以重試或開始下一章。',
  noReplay: '這次潛航沒有可回放的航段。',
  prompts: { move: '移動', accept: '確認', back: '關閉' },
});

// While the screen is up the flight instruments are hidden, so the scene behind it is clean (big_picture.css).
const OPEN_CLASS = 'results-open';

let open = false;

export function resultsOpen() {
  return open;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function points(value) {
  if (value == null) return '—';
  if (value > 0) return `+${value}`;
  if (value < 0) return `−${Math.abs(value)}`;
  return '0';
}

// The launch menu at a given screen and tab (menu/main.js reads ?menu= and ?tab=).
export function menuUrl(href, screen, tab) {
  const url = new URL(href);
  for (const name of ['play', 'replay', 'nointro']) url.searchParams.delete(name);
  url.searchParams.set('menu', screen);
  if (tab) url.searchParams.set('tab', tab);
  return url;
}

// The medal as a thick-outlined tag beside the heading.
function buildMedal() {
  const medal = element('div', 'results-medal');
  medal.setAttribute('role', 'img');
  const label = element('span', 'results-medal-label');
  medal.append(label);
  return { medal, label };
}

// send, getState, getWorld, getSession: app.js accessors. onContracts(): open the in-flight contract board.
// onVisible(open): the card was shown or hidden (app.js switches the music to the results context).
// career: optional career/dive.js runtime; it turns a story-chapter outcome of a work order into a career outcome
// (decorate) and restarts a work order (retry). Career outcomes (kind 'career') also come straight from it.
export function installResults({ send, getState, getWorld, getSession, onContracts, onVisible, readOnly = false,
  career = null }) {
  const watcher = createOutcomeWatcher();
  const log = createFlightLog({ getWorld });
  const root = element('section', 'results-screen');
  root.id = 'resultsScreen';
  root.hidden = true;
  root.setAttribute('role', 'dialog');
  root.setAttribute('aria-modal', 'true');
  root.setAttribute('aria-labelledby', 'resultsHeading');
  const card = element('div', 'results-card');
  const kicker = element('p', 'bp-kicker');
  const headline = element('div', 'results-headline');
  const heading = element('h2', 'bp-title');
  heading.id = 'resultsHeading';
  const { medal, label: medalText } = buildMedal();
  headline.append(heading, medal);
  const title = element('p', 'results-title');
  const reason = element('p', 'results-reason');
  const scoreRow = element('div', 'bp-stats results-score');
  const best = element('p', 'results-best');
  // A YX work order adds one line of licence progress and what it opened (career/results_panel.js).
  const progress = element('div', 'results-progress');
  const unlocks = element('div', 'bp-chips results-unlocks');
  unlocks.id = 'resultsUnlocks';
  const actions = element('nav', 'bp-actions results-actions');
  const note = element('p', 'results-note');
  note.setAttribute('role', 'status');
  card.append(kicker, headline, title, reason, scoreRow, best, progress, unlocks, actions, note);
  // 明細: the score breakdown, what the run earned and, for a work order, the pay slip and the logbook.
  const sheet = createDetailSheet(STRINGS.breakdown);
  const table = element('table');
  sheet.section(STRINGS.breakdown, table).classList.add('results-rows');
  const rewards = element('ul');
  const rewardsBox = sheet.section(STRINGS.rewards, rewards);
  rewardsBox.classList.add('results-rewards');
  const rewardsTitle = rewardsBox.querySelector('h3');
  const careerBox = element('div', 'results-career');
  const careerSection = sheet.section(STRINGS.career, careerBox);
  const footer = element('footer', 'pause-footer results-footer');
  root.append(card, footer);
  document.body.append(root);
  let outcome = null;
  let navigator = null;

  function host() {
    const session = getSession();
    return !session || !!session.is_host;
  }
  function prompts() {
    const items = [['navigate', STRINGS.prompts.move], ['accept', STRINGS.prompts.accept],
      ['back', STRINGS.prompts.back]];
    renderPrompts(footer, items, navigator?.family || 'keyboard');
  }
  function hide() {
    if (!open) return;
    open = false;
    root.hidden = true;
    document.body.classList.remove(OPEN_CLASS);
    sheet.close();
    onVisible?.(false);
    navigator?.setActive(false);
    navigator?.stop();
  }
  function command(action, extra = {}) {
    send({ type: 'operation', action, ...extra });
  }
  function retry() {
    if (outcome.kind === 'career') career?.retry();
    else if (outcome.kind === 'chapter' || outcome.kind === 'drill') command('campaign_start', { chapter: outcome.id });
    else {
      send({ type: 'reset' });
      if (outcome.kind === 'coop') command('mission_mode', { mode: 'inspection_coop' });
    }
    hide();
  }
  function nextChapter() {
    command('campaign_start', { chapter: outcome.next.id });
    hide();
  }
  async function debrief() {
    try {
      await log.openDebrief(outcome.title);
    } catch (error) {
      note.textContent = error.message || STRINGS.noReplay;
    }
  }
  function toMenu() {
    hide();
    document.getElementById('returnMenu')?.click();
  }
  function toList(tab) {
    location.assign(menuUrl(location.href, 'training', tab));
  }
  function button(id, text, handler, { primary = false, disabled = false } = {}) {
    const node = primary ? primaryButton(id, text, { cap: false }).button : linkButton(id, text);
    node.classList.add(primary ? 'results-primary' : 'results-action');
    node.disabled = disabled;
    if (primary) node.dataset.autofocus = '';
    node.addEventListener('click', handler);
    actions.append(node);
    return node;
  }
  function renderActions() {
    actions.replaceChildren();
    const lead = host();
    const kind = outcome.kind;
    if (kind === 'career') {
      button('resultsNext', STRINGS.nextWorkOrder, function nextWorkOrder() {
        location.assign(menuUrl(location.href, 'board'));
      }, { primary: true });
      button('resultsRetry', STRINGS.retryWorkOrder, retry, { disabled: !lead });
    } else if (kind === 'chapter' && outcome.next) {
      const text = STRINGS.nextChapter.replace('{title}', outcome.next.title);
      button('resultsNext', text, nextChapter, { primary: true, disabled: !lead });
    } else if (kind === 'contract') {
      button('resultsNext', STRINGS.nextContract, function nextContract() {
        hide();
        onContracts?.();
      }, { primary: true });
      button('resultsClose', STRINGS.keepExploring, hide);
    }
    if (kind !== 'contract' && kind !== 'career') {
      const retryText = kind === 'chapter' || kind === 'drill' ? STRINGS.retryChapter : STRINGS.retry;
      const primary = !actions.querySelector('.results-primary');
      button('resultsRetry', retryText, retry, { primary, disabled: !lead });
    }
    if (kind === 'scenario') button('resultsMore', STRINGS.moreScenarios, function more() {
      toList('scenarios');
    });
    if (kind === 'drill') button('resultsMore', STRINGS.moreDrills, function more() {
      toList('drills');
    });
    button('resultsDebrief', STRINGS.debrief, debrief, { disabled: log.frames < 2 });
    button('resultsMenu', STRINGS.menu, toMenu);
    if (kind !== 'contract') button('resultsClose', STRINGS.close, hide);
    // 明細 sits after the primary button and the first secondary action.
    const details = linkButton('resultsDetails', DETAILS_LABEL);
    details.classList.add('results-action');
    details.addEventListener('click', sheet.open);
    actions.insertBefore(details, actions.children[2] || null);
    const notes = [];
    if (!lead && kind !== 'contract') notes.push(STRINGS.hostOnly);
    if (kind === 'chapter' && !outcome.next) notes.push(STRINGS.storyDone);
    note.textContent = notes.join(' ');
  }
  function renderRows() {
    table.replaceChildren();
    for (const row of outcome.rows) {
      const line = element('tr');
      line.dataset.row = row.id;
      line.append(element('th', '', row.label), element('td', '', row.detail), element('td', 'results-points',
        points(row.points)));
      table.append(line);
    }
  }
  function renderRewards() {
    const career = outcome.career ? deliverableLines(outcome.career) : [];
    rewardsTitle.textContent = outcome.career ? DELIVERABLES_TITLE : STRINGS.rewards;
    rewards.replaceChildren(...[...outcome.rewards, ...career].map(function item(text) {
      return element('li', '', text);
    }));
    if (!outcome.rewards.length && !career.length) rewards.append(element('li', 'menu-help', STRINGS.noRewards));
  }
  function show(next) {
    outcome = next;
    const record = recordResult(outcome);
    root.dataset.kind = outcome.kind;
    root.dataset.success = String(outcome.success);
    kicker.textContent = [kindLabel(outcome.kind), formatTime(outcome.elapsed)].join(' · ');
    let headingText = outcome.success ? STRINGS.success : STRINGS.failure;
    if (outcome.heading) headingText = outcome.heading;
    else if (outcome.kind === 'contract') headingText = STRINGS.contractDone;
    fitTitle(heading, headingText);
    sheet.setTitle(outcome.title || headingText);
    title.textContent = outcome.title;
    reason.textContent = outcome.reason;
    reason.hidden = !outcome.reason;
    medal.dataset.medal = outcome.medal;
    medalText.textContent = medalLabel(outcome.medal);
    medal.setAttribute('aria-label', medalLabel(outcome.medal));
    // One huge number: what the work order paid, else the score.
    const headlineCareer = careerHeadline(outcome);
    scoreRow.replaceChildren();
    if (headlineCareer) {
      const pay = stat(...headlineCareer.pay);
      pay.id = 'resultsPay';
      scoreRow.append(pay);
    }
    scoreRow.append(stat(STRINGS.score, String(outcome.score)));
    progress.replaceChildren(...(headlineCareer ? [headlineCareer.licence] : []));
    unlocks.replaceChildren(...(headlineCareer?.unlocks || []).map(function unlockChip(text) {
      return chip(text, 'ok');
    }));
    if (record.isBest && record.previous != null) best.textContent = STRINGS.newBest;
    else if (record.isBest) best.textContent = STRINGS.firstBest;
    else best.textContent = record.best != null ? STRINGS.best.replace('{best}', String(record.best)) : '';
    best.dataset.new = String(record.isBest);
    renderRows();
    renderRewards();
    renderCareerPanel(careerBox, outcome);
    careerSection.hidden = careerBox.hidden;
    renderActions();
    open = true;
    root.hidden = false;
    document.body.classList.add(OPEN_CLASS);
    onVisible?.(true);
    navigator?.setActive(true);
    navigator?.start();
    prompts();
    if (outcome.career?.exam?.passed) {
      awardLicenceFromSummary(outcome.career, loadCareer());
    }
    requestAnimationFrame(function focusActions() {
      if (navigator) navigator.focusFirst(actions);
      else actions.querySelector('button:not(:disabled)')?.focus({ preventScroll: true });
    });
    document.dispatchEvent(new CustomEvent('rov-run-result', { detail: outcome }));
  }
  function update(state) {
    if (readOnly) return;
    log.update(state);
    const ended = watcher.observe(state, getWorld());
    if (ended) show(career ? career.decorate(ended) : ended);
  }
  loadControllerDatabase().then(function ready(database) {
    navigator = createMenuNavigator({
      database,
      handlers: {
        scope() {
          return card;
        },
        back: hide,
        family: prompts,
      },
    });
    if (open) {
      navigator.setActive(true);
      navigator.start();
    }
  });
  const api = {
    update,
    show,
    hide,
    get open() {
      return open;
    },
    get outcome() {
      return outcome;
    },
  };
  // Browser checks read the last outcome here.
  window.__results = api;
  return api;
}
