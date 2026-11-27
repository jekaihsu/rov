// Deployment checklist, tended launch, recovery and post-dive log. The server owns progression and safety gates
// (qysim/procedure.py); this module only renders the current phase and sends the operator's confirmations.
// Whether the full procedure runs is the `deployProcedure` fidelity item (real: full, assisted: quick); `?nointro`
// always skips it. Gamepad and keyboard navigation use the menu-context rows of input/bindings.js while the
// checklist has something to press.
// Presentation (procedure.css): a low column at the lower left on a scrim gradient, never a box over the scene.
// On deck it shows the current item large, the finished ones as a count and one primary action. During the dive
// nothing stays on screen: recovery is an entry of the pause menu (pauseActions), announced by a short prompt when
// the vehicle comes back to the surface. After the dive the same column carries the log and a few big numbers.
// Deck flow (servers that report `flow:"deck"`): only real, observable checks on the aft deck, each with a reaction
// and a camera move (deck_steps.js column, deck_stage.js scene); routine items come from the crew radio
// (crew_radio.js). Older servers ignore the flow request and get the legacy ten-item column below unchanged.
// Order with the launch intro (deploy_intro.js): the intro opens on the aft deck and holds during the checklist;
// the A-frame launch cinematic plays when the operator lowers the vehicle (phase launch -> water_check), then the
// water check and dive follow. Without the procedure the intro plays at scenario start exactly as before.
import {getFidelity} from '../fidelity.js';
import {PROCEDURE_ITEM} from './fidelity_item.js';
import {createSurfaceWatch, recoveryReadiness} from './recovery.js';
import {beginFields, createEventWatch} from './deck_flow.js';
import {deckSignature, renderDeckChecks, renderDeckLaunch} from './deck_steps.js';
import {createDeckStage} from './deck_stage.js';
import {callFor, createCrewRadio, faultText} from './crew_radio.js';
import { checklistNavigable } from './navigable.js';
import { localize } from '../i18n/index.js';

export { checklistNavigable } from './navigable.js';

const STRINGS = localize('procedure.index', {
  title: '潛前檢查與回收',
  // Engineering detail (hover only): the player path does not read like an unfinished product.
  provisional: '短測為模擬診斷，每顆 2 秒；禁止拋擲。',
  provisionalDetail: '上電順序、提示音、燈號與回收速度為暫定值，待實測。',
  checks: ['外觀、密封與穿艙件已檢查', '纜線接頭與固定環已確認', '配重與配平已確認',
    '岸上供電與載具上電已確認', '通訊已確認', '相機影像已確認', '燈光已確認',
    '逐顆推進器短測完成', '深度零點與羅盤已確認', '入水、人員離開後才解鎖，已確認'],
  keys: ['seals', 'connector', 'trim', 'power', 'communication', 'camera', 'lights',
    'thrusters', 'instruments', 'unlock'],
  kickers: {
    checks: '潛前檢查',
    launch: '下水',
    recovering: '回收',
    post: '潛後處理',
  },
  progress: '{done} / {total}',
  confirm: '確認',
  skip: '跳過未完成檢查（可能引發故障並扣分）',
  tender: '與纜線手確認就緒',
  lower: '選上游點，以纜線緩放入水',
  lowerAction: '緩放入水',
  waterTitle: '入水確認',
  water: '影像、配平與功能正常；人員已離開',
  waterAction: '確認，開始作業',
  recover: '收纜回收',
  recoverReady: '水面上鎖後收纜回收',
  recoverDepth: '浮上水面（0.8 m 內）後才能收纜回收。',
  recoverLock: '上鎖後才能收纜回收。',
  // Pause-menu label while the server would still refuse recovery; the full reason is its tooltip.
  recoverPending: {depth: '{label} · 先浮上水面', lock: '{label} · 先上鎖'},
  surfacedReady: '已回到水面 · 開啟暫停選單即可收纜回收',
  surfacedLock: '已回到水面 · 上鎖後可在暫停選單收纜回收',
  recoveringTitle: '收纜中',
  rinse: '已以淡水沖洗',
  inspect: '潛後檢查完成',
  logTitle: '潛水日誌',
  save: '儲存日誌',
  export: '匯出日誌',
  notes: '潛水註記',
  test: '短測推進器',
  testing: '短測中…',
  stats: {elapsed: '作業時間', depth: '最大深度', cable: '最大纜長', penalty: '扣分'},
  units: {depth: 'm', cable: 'm'},
  fault: '未檢項目發生故障，已扣分，必要時中止作業收纜回收。',
  dry: '離水運轉超過 30 秒，已告警並扣分。',
  recovering: '收纜中，洋流與模擬浪況會降低回收速度',
  complete: '潛後處理完成',
  onDeck: '載具在工作船後甲板上，尚未入水；完成檢查、放入水中並確認後才能解鎖。',
});
// Launch steps: tender ready, lower into the water, water check.
const LAUNCH_STEPS = 3;
// Phases whose column carries the post-dive numbers, and the steps counted in it.
const POST_STEPS = ['post', 'inspect', 'log'];
const POST_PHASES = new Set([...POST_STEPS, 'complete']);
// How long a dive prompt stays before it fades (ms).
const PROMPT_MS = 7000;
const OPEN_CLASS = 'procedure-open';

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function downloadJson(data, name) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(function revoke() {
    URL.revokeObjectURL(url);
  }, 1000);
}

function clock(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  return `${minutes}:${String(total % 60).padStart(2, '0')}`;
}

function progress(done, total) {
  return STRINGS.progress.replace('{done}', done).replace('{total}', total);
}

/**
 * Pilot-log lines (tether, silt, link, power, sensor...) gathered from `state.log` during the dive. The server
 * only streams the last 8 lines, so they are accumulated here for the dive-log export.
 */
function createPilotLog(limit = 2000) {
  const rows = [];
  const seen = new Set();
  function collect(log) {
    for (const row of log || []) {
      const key = `${row.t}|${row.kind}|${row.text}`;
      if (seen.has(key)) continue;
      seen.add(key);
      rows.push(row);
    }
    if (rows.length > limit) rows.splice(0, rows.length - limit);
  }
  function clear() {
    rows.length = 0;
    seen.clear();
  }
  function lines() {
    return rows.slice();
  }
  return {collect, clear, lines};
}

// A short line in the upper middle during the dive (surfaced, fault); it fades by itself and takes no input.
function createDivePrompt() {
  const node = element('p', 'procedure-prompt');
  node.id = 'procedurePrompt';
  node.setAttribute('role', 'status');
  node.hidden = true;
  document.body.append(node);
  let timer = null;
  function hide() {
    clearTimeout(timer);
    node.hidden = true;
  }
  function show(text, level = 'info') {
    clearTimeout(timer);
    node.textContent = text;
    node.dataset.level = level;
    node.hidden = false;
    timer = setTimeout(hide, PROMPT_MS);
  }
  return {show, hide};
}

// deck: {getIntro, rov, getRotors} from the viewer, for the deck flow's scene reactions (deck_stage.js).
export function installProcedure({send, readOnly = false, deck = null}) {
  const query = new URLSearchParams(location.search);
  const fidelity = getFidelity();
  let begunGeneration;
  let latest;
  let latestState;
  let launchIntro = null;
  let lastPhase = null;
  let signature;
  let faultsSeen = 0;
  let radioProcedure = null;
  // data-focus key of the control the keyboard or pad last stood on; restored after each re-render.
  let focusKey = null;
  const pilotLog = createPilotLog();
  const surfaceWatch = createSurfaceWatch();
  const prompt = createDivePrompt();
  const crewRadio = createCrewRadio();
  const calls = createEventWatch();
  const stage = deck?.rov ? createDeckStage(deck) : null;
  const panel = element('section', 'procedure-panel');
  panel.id = 'procedurePanel';
  panel.hidden = true;
  panel.setAttribute('aria-label', STRINGS.title);
  document.body.append(panel);
  panel.addEventListener('pointerdown', function pointerUsed() {
    delete panel.dataset.nav;
  });
  panel.tabIndex = -1;
  panel.addEventListener('focusin', function remember(event) {
    if (event.target !== panel) focusKey = event.target.dataset.focus || null;
  });
  function wanted() {
    return !readOnly && query.get('chapter') !== 'prologue' && !query.has('nointro') && fidelity.get(PROCEDURE_ITEM) === 'full';
  }
  function command(action, extra = {}) {
    send({type: 'procedure', action, ...extra});
  }
  function actionButton(className, text, key, run) {
    const node = element('button', className, text);
    node.type = 'button';
    node.dataset.focus = key;
    node.onclick = run;
    return node;
  }
  function primary(text, action, extra) {
    const node = actionButton('pp-primary', text, 'primary', function activate() {
      command(action, extra);
    });
    node.id = 'procedurePrimary';
    return node;
  }
  function link(text, key, run) {
    return actionButton('pp-link', text, key, run);
  }
  function header(kicker, count, title) {
    const top = element('p', 'pp-kicker');
    top.title = `${STRINGS.provisional}\n${STRINGS.provisionalDetail}`;
    top.append(element('span', '', kicker));
    if (count) top.append(element('span', 'pp-count', count));
    return [top, element('h2', 'pp-title', title)];
  }
  function note(text, level = '') {
    const node = element('p', 'pp-note', text);
    if (level) node.dataset.level = level;
    return node;
  }
  function warnings(p) {
    const lines = [];
    if (p.dry_seconds > 30) lines.push(note(STRINGS.dry, 'warn'));
    if (p.events.some(function fault(event) {
      return event.action === 'fault';
    })) lines.push(note(STRINGS.fault, 'warn'));
    if (p.penalty > 0 && !POST_PHASES.has(p.phase)) {
      lines.push(note(`${STRINGS.stats.penalty} ${p.penalty}`, 'warn'));
    }
    return lines;
  }
  function thrusterTests(p) {
    const group = element('div', 'pp-tests');
    group.setAttribute('role', 'group');
    group.setAttribute('aria-label', STRINGS.test);
    group.append(element('span', 'pp-tests-label', p.diagnostic > 0 ? STRINGS.testing : STRINGS.test));
    for (let index = 0; index < p.thrusters; index++) {
      const test = link(String(index + 1), `test-${index}`, function pulse() {
        command('test', {index});
      });
      test.classList.add('pp-test');
      test.setAttribute('aria-label', `${STRINGS.test} ${index + 1}`);
      if (p.tests.includes(index)) test.dataset.done = 'true';
      test.disabled = p.tests.includes(index) || p.diagnostic > 0;
      group.append(test);
    }
    return group;
  }
  // Builders handed to the deck-flow column (deck_steps.js).
  const deckUi = {
    header,
    note,
    primary,
    link,
    command,
    warnings,
    count: function count(p) {
      return progress(p.checked.length, p.order.length);
    },
  };
  function renderChecks(p) {
    const index = p.checked.length;
    const parts = header(STRINGS.kickers.checks, progress(index, STRINGS.keys.length), STRINGS.checks[index]);
    if (index === 0) parts.push(note(STRINGS.onDeck));
    const go = primary(STRINGS.confirm, 'check', {key: STRINGS.keys[index]});
    if (STRINGS.keys[index] === 'thrusters') {
      parts.push(thrusterTests(p));
      go.disabled = p.tests.length < p.thrusters;
    }
    parts.push(...warnings(p), go, link(STRINGS.skip, 'skip', function skip() {
      command('skip');
    }));
    return parts;
  }
  function renderLaunch(p) {
    const count = progress(p.confirmed ? 2 : 1, LAUNCH_STEPS);
    const parts = header(STRINGS.kickers.launch, count, p.confirmed ? STRINGS.lower : STRINGS.tender);
    parts.push(note(STRINGS.onDeck), ...warnings(p));
    if (p.confirmed) parts.push(primary(STRINGS.lowerAction, 'lower', {point: 'upstream'}));
    else parts.push(primary(STRINGS.confirm, 'tender'));
    return parts;
  }
  function renderStats(p) {
    const row = element('div', 'pp-stats');
    const values = [
      ['elapsed', clock(p.elapsed), ''],
      ['depth', Number(p.max_depth).toFixed(1), STRINGS.units.depth],
      ['cable', Number(p.max_cable).toFixed(0), STRINGS.units.cable],
      ['penalty', String(p.penalty), ''],
    ];
    for (const [key, value, unit] of values) {
      const block = element('div', 'pp-stat');
      const line = element('span', 'pp-stat-value');
      line.append(element('b', '', value));
      if (unit) line.append(element('small', '', unit));
      block.append(line, element('span', 'pp-stat-label', STRINGS.stats[key]));
      if (key === 'penalty' && p.penalty > 0) block.dataset.level = 'warn';
      row.append(block);
    }
    return row;
  }
  function renderPost(p) {
    const step = POST_STEPS.indexOf(p.phase);
    const count = step >= 0 ? progress(step + 1, POST_STEPS.length) : '';
    const titles = {post: STRINGS.rinse, inspect: STRINGS.inspect, log: STRINGS.logTitle, complete: STRINGS.complete};
    const parts = header(STRINGS.kickers.post, count, titles[p.phase]);
    parts.push(renderStats(p), ...warnings(p));
    if (p.phase === 'post') parts.push(primary(STRINGS.confirm, 'rinse'));
    if (p.phase === 'inspect') parts.push(primary(STRINGS.confirm, 'inspect'));
    if (p.phase === 'log') {
      const notes = element('textarea', 'pp-notes');
      notes.placeholder = STRINGS.notes;
      notes.dataset.focus = 'notes';
      notes.setAttribute('aria-label', STRINGS.notes);
      const save = primary(STRINGS.save, 'save');
      save.onclick = function saveLog() {
        command('save', {notes: notes.value});
      };
      parts.push(notes, save);
    }
    if (p.phase === 'complete') {
      const download = actionButton('pp-primary', STRINGS.export, 'primary', function exportLog() {
        downloadJson({...latest, pilot_log: pilotLog.lines()}, 'dive-log.json');
      });
      download.id = 'procedurePrimary';
      parts.push(download);
    }
    return parts;
  }
  function renderPhase(p) {
    if (p.flow === 'deck' && p.phase === 'checks') return renderDeckChecks(p, deckUi);
    if (p.flow === 'deck' && p.phase === 'launch') return renderDeckLaunch(p, deckUi);
    if (p.phase === 'checks') return renderChecks(p);
    if (p.phase === 'launch') return renderLaunch(p);
    if (p.phase === 'water_check') {
      const count = progress(LAUNCH_STEPS, LAUNCH_STEPS);
      return [...header(STRINGS.kickers.launch, count, STRINGS.waterTitle), note(STRINGS.water), ...warnings(p),
        primary(STRINGS.waterAction, 'water_confirm')];
    }
    if (p.phase === 'recovering') {
      return [...header(STRINGS.kickers.recovering, '', STRINGS.recoveringTitle), note(STRINGS.recovering),
        ...warnings(p)];
    }
    if (POST_PHASES.has(p.phase)) return renderPost(p);
    return [];
  }
  function focusables() {
    return [...panel.querySelectorAll('button:not(:disabled), textarea')];
  }
  // After a re-render keep the keyboard or pad where it was, or put it on the primary action, so a run of
  // confirm presses walks the checklist. Never falls back onto the skip action; with nothing to press the panel
  // itself holds focus until the next render. Focus elsewhere on the page is left alone.
  function restoreFocus() {
    const wantedKey = focusKey;
    const items = focusables();
    const target = items.find(function same(item) {
      return item.dataset.focus === wantedKey;
    }) || items.find(function primaryItem(item) {
      return item.id === 'procedurePrimary';
    }) || items.find(function notSkip(item) {
      return item.dataset.focus !== 'skip';
    });
    if (target) target.focus({preventScroll: true});
    else panel.focus({preventScroll: true});
    focusKey = wantedKey;
  }
  function render(p) {
    const active = document.activeElement;
    const hadFocus = panel.contains(active) || !active || active === document.body;
    if (panel.dataset.phase !== p.phase) focusKey = null;
    panel.dataset.phase = p.phase;
    panel.dataset.stage = POST_PHASES.has(p.phase) ? 'post' : 'deck';
    panel.replaceChildren(...renderPhase(p));
    if (hadFocus && !panel.hidden) restoreFocus();
  }
  function setVisible(visible) {
    panel.hidden = !visible;
    document.body.classList.toggle(OPEN_CLASS, visible);
    if (!visible) delete panel.dataset.nav;
  }
  // During the dive: nothing on screen, only a short prompt when the vehicle surfaces or a skipped check fails.
  function watchDive(state, p) {
    const faults = p.events.filter(function fault(event) {
      return event.action === 'fault';
    });
    if (faults.length > faultsSeen && p.phase === 'diving') {
      prompt.show(faultText(faults.at(-1)) || STRINGS.fault, 'warn');
    }
    faultsSeen = faults.length;
    if (surfaceWatch.update(state) === 'surfaced') {
      prompt.show(state.locked ? STRINGS.surfacedReady : STRINGS.surfacedLock);
    }
    if (p.phase !== 'diving') prompt.hide();
  }
  // The setting is read when a scenario (re)loads, so changing it mid-dive never teleports the vehicle.
  function update(state) {
    if (readOnly) return;
    if (query.get('mission') === 'campaign' && !state.campaign?.chapter) return;
    if (begunGeneration !== state.control_generation) {
      begunGeneration = state.control_generation;
      pilotLog.clear();
      faultsSeen = 0;
      if (!state.campaign?.directed && wanted() && !state.procedure?.active) command('begin', beginFields(query));
    }
    latestState = state;
    const p = state.procedure;
    stage?.update(p?.active ? p : null);
    if (!p?.active) {
      setVisible(false);
      prompt.hide();
      return;
    }
    // A new procedure (scenario reload) starts its radio afresh. control_generation is not used for this: an input
    // failsafe lock on a slow page raises it without restarting anything.
    if (radioProcedure !== p.started_at) {
      radioProcedure = p.started_at;
      calls.clear();
      crewRadio.clear();
    }
    for (const event of calls.fresh(p.events)) crewRadio.say(callFor(event));
    latest = p;
    pilotLog.collect(state.log);
    if (p.phase === 'water_check' && lastPhase === 'launch' && launchIntro) {
      const play = launchIntro;
      launchIntro = null;
      play();
    }
    lastPhase = p.phase;
    watchDive(state, p);
    setVisible(p.phase !== 'diving');
    const nextSignature = JSON.stringify([p.phase, p.checked, p.tests, p.confirmed, p.diagnostic > 0, p.penalty,
      p.dry_seconds > 30, ...(p.flow === 'deck' ? deckSignature(p) : [])]);
    if (signature === nextSignature) return;
    signature = nextSignature;
    render(p);
  }
  function navigable() {
    return checklistNavigable({
      hidden: panel.hidden,
      phase: latest?.phase,
      focusableCount: focusables().length,
    });
  }
  function moveFocus(step) {
    const items = focusables();
    if (!items.length) return;
    panel.dataset.nav = 'input';
    const index = items.indexOf(document.activeElement);
    if (index < 0) {
      restoreFocus();
      return;
    }
    items[(index + step + items.length) % items.length].focus();
  }
  // Menu-context rows (input/bindings.js) own the pad while the checklist is open; flight is locked on deck anyway.
  function bindInput(input) {
    function step(direction) {
      return {enabled: navigable, run: function move() {
        moveFocus(direction);
      }};
    }
    input.registerActions({
      menuUp: step(-1),
      menuDown: step(1),
      menuLeft: step(-1),
      menuRight: step(1),
      accept: {enabled: navigable, run: function activate() {
        if (focusables().includes(document.activeElement)) {
          panel.dataset.nav = 'input';
          document.activeElement.click();
        } else moveFocus(0);
      }},
    });
  }
  // Entries for the pause menu (menu/pause.js extraActions): recovery during the dive, with the reason when the
  // server would still refuse it.
  function pauseActions() {
    const readiness = recoveryReadiness(latestState);
    if (!readiness) return [];
    const reasons = {depth: STRINGS.recoverDepth, lock: STRINGS.recoverLock, ready: STRINGS.recoverReady};
    return [{
      id: 'procedure-recover',
      label: (STRINGS.recoverPending[readiness] || '{label}').replace('{label}', STRINGS.recover),
      disabled: readiness !== 'ready',
      title: reasons[readiness],
      run: function recover() {
        command('recover');
      },
    }];
  }
  // With the procedure the intro opens on the aft deck and holds there through the checklist, so the operator
  // sees the vehicle where it really is; lowering it releases the launch. Without the procedure it plays now.
  function startIntro(play) {
    if (!wanted()) {
      play();
      return;
    }
    launchIntro = null;
    Promise.resolve(play(true)).then(function heldOnDeck(release) {
      launchIntro = release || null;
    });
  }
  /** Deck-flow scene and radio state for the browser checks. */
  function debug() {
    return {stage: stage?.debug() || null, radio: crewRadio.debug()};
  }
  globalThis.__procedure = debug;
  return {update, startIntro, bindInput, pauseActions, canNavigate: navigable, debug, radio: crewRadio};
}
