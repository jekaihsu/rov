// In-flight new-player hints on the clean game HUD (not in the engineering drawer). One small card on the left of
// the view says what to do next — unlock, move and turn, depth hold, lights, photo, the objectives peek and the
// pause menu — with the player's own bindings drawn as glyph caps for the device in use, ticks the step off from
// telemetry (onboarding_model.js) and fades out. The first time the tether pulls, the DVL loses the bottom or the
// water turns murky, a tip says how to handle it. Hints wait while the launch cinematic, the deck procedure, the
// story radio, the pause menu or the results are up. The pause menu lists the same steps as 操作教學, and the
// settings turn the hints off or show them again (onboarding_settings.js).
import { actionKey, axisChannel, bindingRow, pilotAxisKeys } from '../input/bindings.js';
import { deviceFamily, glyph, padNames } from '../input/glyphs.js';
import { pauseMenuOpen } from '../menu/pause.js';
import { dvlReason } from '../hud/assist_pill.js';
import { resultsOpen } from './results.js';
import {
  MOVES,
  ONBOARDING_CHANGED,
  STEPS,
  createTracker,
  currentStep,
  loadProgress,
  observe,
  pendingTip,
  saveProgress,
  stepsDone,
  tipActive,
} from './onboarding_model.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('play.onboarding', {
  kicker: '新手提示 {n}/{total}',
  tipKicker: '第一次遇到',
  dismiss: '略過這則提示',
  hold: '按住',
  sticks: { left: '左搖桿', right: '右搖桿' },
  directions: { ud: '↑↓', lr: '←→' },
  dpad: '十字鍵',
  padButtons: ['LB', 'RB', 'LT', 'RT', 'View', 'Menu', 'L3', 'R3'],
  steps: {
    unlock: ['解鎖推進器', '解鎖', '上鎖時推進器不出力。確認前方淨空再解鎖；要停下來時可以再上鎖。'],
    move: ['移動與轉向', '', '小幅推桿、慢慢來：推桿是推力，鬆開後機體靠水阻慢慢停下，洋流仍會推著走。'],
    depth: ['定深', '開關定深', '定深開著時，鬆開升降就會維持目前深度。試著關掉再打開。'],
    light: ['燈光', '切換燈光', '越深越暗。燈光照亮前方；在混濁水中光會被懸浮粒子反射，必要時調暗。'],
    photo: ['拍照', '拍照', '對準目標拍下來。照片存進收藏，任務的證據也靠它。'],
    objectives: ['任務目標', '查看目標', '速覽卡會短暫顯示目標，不會打斷操控；其他方向是系統、地圖與鍵位。'],
    pause: ['暫停選單', '開啟暫停選單', '暫停選單裡有目前目標、設定，以及隨時可看的操作教學。'],
  },
  depthOff: '定深關著時機體會慢慢浮沉。打開它，鬆開升降就能維持深度。',
  moveAssisted: '小幅推桿、慢慢來：輔助開著時，鬆開搖桿機體會主動煞停；洋流強時仍可能被推著走。',
  moves: { surge: '前進／後退', yaw: '右轉／左轉', heave: '上升／下潛' },
  tips: {
    tether: ['纜線張力升高', '纜線被拉緊或卡到障礙了。停止推桿，沿來時的路線慢慢退回，讓纜線放鬆。'],
    dvl: ['DVL 失去對底鎖定', '速度與定點輔助需要 DVL 量到海床，現在暫時改為手動推力。'],
    visibility: ['能見度很低', '放慢速度，別讓推進器揚起海床泥沙；靠深度、航向與聲納判斷位置，等泥沙沉降。'],
  },
  tutorial: {
    title: '操作教學',
    intro: '基本操作與目前的按鍵。完成的項目打勾；新手提示可在設定的「介面」重新顯示。',
    done: '已完成',
    open: '未完成',
  },
});
// A hint waits this long after it becomes relevant, so it does not flash between two quick states.
const APPEAR_MS = 900;
// A completed step stays on screen with its tick this long before it fades.
const DONE_MS = 2000;
const TIP_MIN_MS = 8000;
const TIP_MAX_MS = 15000;
const TIP_CLEAR_MS = 3000;
const ACTIONS = { unlock: 'lock', depth: 'depth', light: 'light', photo: 'photo', objectives: 'up', pause: 'pause' };

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

const ARROWS = ['↑', '↓', '←', '→'];

function keyCap(caption) {
  return glyph(0, 'keyboard', caption);
}

// A word beside a cap (左搖桿 [↑↓], 十字鍵 [↑]): glyph caps size for short Latin captions, not CJK words.
function namedCap(name, caption) {
  const word = document.createElement('span');
  word.className = 'ob-cap-name';
  word.textContent = name;
  return word.outerHTML + keyCap(caption);
}

// Cap of a standard pad button for a controller family: face glyphs, shoulders and menu buttons, the d-pad.
function padButtonCap(index, family) {
  if (index < 4) return glyph(index, family);
  if (index >= 12 && index <= 15) return namedCap(STRINGS.dpad, ARROWS[index - 12]);
  return keyCap(padNames(family)?.[index] || STRINGS.padButtons[index - 4] || String(index + 1));
}

// Caps for one pad source (`b3`, `-a1`, `[b7, b6]`). Stick axes are named by stick and direction.
function padSourceCaps(source, family) {
  const parts = Array.isArray(source) ? source : [source];
  const caps = [];
  for (const part of parts) {
    const match = /^[+-]?([ab])(\d+)~?$/.exec(part || '');
    if (!match) continue;
    const index = Number(match[2]);
    if (match[1] === 'b') {
      caps.push(padButtonCap(index, family));
      continue;
    }
    const stick = index < 2 ? STRINGS.sticks.left : STRINGS.sticks.right;
    caps.push(namedCap(stick, index % 2 ? STRINGS.directions.ud : STRINGS.directions.lr));
  }
  return caps;
}

// HTML caps for an action on the current device: the bound pad source, or the first bound key.
export function actionCaps(action, family, controls) {
  if (family !== 'keyboard') {
    const source = controls.bindings?.[action] ?? bindingRow(action)?.pad;
    const caps = padSourceCaps(source, family);
    if (!caps.length) return '';
    const hold = bindingRow(action)?.gesture === 'hold' ? `<span class="ob-hold">${STRINGS.hold}</span>` : '';
    return hold + caps.join('');
  }
  const key = actionKey(action, controls.rows);
  return key ? keyCap(key) : '';
}

// HTML caps for a pilot axis (surge, yaw, heave) in the operation mode, positive direction first.
export function axisCaps(axis, family, controls) {
  const mode = controls.operationMode;
  if (family === 'keyboard') return pilotAxisKeys(axis, controls.rows, mode).map(keyCap).join('');
  const drive = axisChannel(axis, mode);
  if (!drive) return '';
  const source = controls.bindings?.[drive.channel] ?? bindingRow(drive.channel)?.pad;
  if (Array.isArray(source) && drive.sign < 0) return padSourceCaps([source[1], source[0]], family).join('');
  return padSourceCaps(source, family).join('');
}

// Whether another layer owns the screen right now; hints wait until it is gone.
function screenBusy() {
  if (pauseMenuOpen() || resultsOpen()) return true;
  return !!document.querySelector('.viewport.intro, #procedurePanel:not([hidden]), .story-radio:not([hidden]), '
    + '.brand-card-overlay');
}

function peekCard() {
  if (!document.body.classList.contains('hud-peek')) return null;
  const card = document.getElementById('flightPeek');
  return card?.classList.contains('visible') ? Number(card.dataset.card) : null;
}

// One line of a hint: HTML caps, what they do, and whether that part is already done.
function lineOf(caps, label, done) {
  return { caps, label, done };
}

// input: the object installInput returned (hudState() gives bindings, key rows and operation mode).
export function installOnboarding({ input, readOnly = false }) {
  let progress = loadProgress();
  const tracker = createTracker();
  // The device the player last used, announced by the input layer (rov-input-device); keyboard until then.
  let family = 'keyboard';
  const root = element('aside', 'onboarding-hint');
  root.id = 'onboardingHint';
  root.hidden = true;
  root.setAttribute('role', 'status');
  root.setAttribute('aria-live', 'polite');
  const head = element('div', 'ob-head');
  const kicker = element('span', 'ob-kicker');
  const dismiss = element('button', 'ob-dismiss', '×');
  dismiss.type = 'button';
  dismiss.id = 'onboardingDismiss';
  dismiss.title = STRINGS.dismiss;
  dismiss.setAttribute('aria-label', STRINGS.dismiss);
  head.append(kicker, dismiss);
  const title = element('strong', 'ob-title');
  const lines = element('ul', 'ob-lines');
  const body = element('p', 'ob-body');
  root.append(head, title, lines, body);
  document.body.append(root);
  // shown: {kind: 'step'|'tip', id, since, doneAt, clearAt}; candidate: what wants to show and since when.
  let shown = null;
  let candidate = null;
  let signature = '';
  let lastState = null;

  function controls() {
    const state = input?.hudState?.() || {};
    return { bindings: state.bindings, rows: state.keyRows, operationMode: state.operationMode || 'ROV_USA' };
  }
  function stepContent(id, state) {
    const [heading, action, text] = STRINGS.steps[id];
    const keys = controls();
    if (state?.operation_mode) keys.operationMode = state.operation_mode;
    if (id === 'move') {
      const assisted = (state?.rc?.assist ?? state?.assist?.level ?? 0) > 0;
      return {
        heading,
        text: assisted ? STRINGS.moveAssisted : text,
        lines: MOVES.map(function moveLine(axis) {
          return lineOf(axisCaps(axis, family, keys), STRINGS.moves[axis], progress.moves[axis]);
        }),
      };
    }
    const depthText = id === 'depth' && !(state?.rc?.keep_depth ?? state?.keep_depth) ? STRINGS.depthOff : text;
    return { heading, text: depthText, lines: [lineOf(actionCaps(ACTIONS[id], family, keys), action, false)] };
  }
  function tipContent(id, state) {
    const [heading, text] = STRINGS.tips[id];
    const reason = id === 'dvl' ? dvlReason(state) : null;
    return { heading, text: reason ? `${text} ${reason.help}` : text, lines: [] };
  }
  function render(content, done) {
    const next = JSON.stringify([shown.kind, shown.id, content, done, family, stepsDone(progress)]);
    if (next === signature) return;
    signature = next;
    root.dataset.kind = shown.kind;
    root.dataset.hint = shown.id;
    root.dataset.done = String(done);
    kicker.textContent = shown.kind === 'tip' ? STRINGS.tipKicker
      : STRINGS.kicker.replace('{n}', String(STEPS.indexOf(shown.id) + 1)).replace('{total}', String(STEPS.length));
    title.textContent = content.heading;
    lines.replaceChildren(...content.lines.map(function line(item) {
      const row = element('li');
      row.dataset.done = String(done || item.done);
      const caps = element('span', 'ob-caps');
      caps.innerHTML = item.caps;
      row.append(caps, element('span', 'ob-label', item.label));
      return row;
    }));
    lines.hidden = !content.lines.length;
    body.textContent = content.text;
  }
  function hide() {
    shown = null;
    signature = '';
    root.classList.remove('visible');
    root.hidden = true;
  }
  function show(kind, id, now) {
    shown = { kind, id, since: now, doneAt: 0, clearAt: 0 };
    root.hidden = false;
    requestAnimationFrame(function fadeIn() {
      root.classList.add('visible');
    });
    if (kind === 'tip') {
      progress.tips[id] = true;
      saveProgress(progress);
    }
  }
  // What should be on screen now, ignoring the appear delay: a due tip first, else the next basic step.
  function wanted(state) {
    if (!progress.enabled || readOnly || !state || state.paused || screenBusy()) return null;
    // A USB hand controller or the SDK flies the vehicle: the key and pad hints would be wrong.
    const step = state.controller || state.remote_control ? null : currentStep(progress);
    const tip = pendingTip(progress, state, step);
    if (tip) return { kind: 'tip', id: tip };
    return step ? { kind: 'step', id: step } : null;
  }
  function tipFinished(state, now) {
    const age = now - shown.since;
    if (age >= TIP_MAX_MS) return true;
    if (tipActive(shown.id, state)) {
      shown.clearAt = 0;
      return false;
    }
    shown.clearAt ||= now;
    return age >= TIP_MIN_MS && now - shown.clearAt >= TIP_CLEAR_MS;
  }
  function updateShown(state, now) {
    if (screenBusy() || !progress.enabled) {
      hide();
      return;
    }
    if (shown.kind === 'tip') {
      if (tipFinished(state, now)) hide();
      else render(tipContent(shown.id, state), false);
      return;
    }
    const done = !!progress.steps[shown.id];
    if (done && !shown.doneAt) shown.doneAt = now;
    if (shown.doneAt && now - shown.doneAt >= DONE_MS) {
      hide();
      return;
    }
    // A tip that comes due replaces a step hint that is still waiting to be done.
    if (!done && pendingTip(progress, state, shown.id)) {
      hide();
      return;
    }
    render(stepContent(shown.id, state), done);
  }
  function update(state) {
    if (readOnly) return;
    // The cold open (story/cold_open.js) gives its own single hint; its flying does not tick the steps off.
    if (document.body.classList.contains('cold-open')) {
      if (shown) hide();
      return;
    }
    lastState = state || lastState;
    const now = performance.now();
    const completed = observe(progress, tracker, state, {
      pauseOpen: pauseMenuOpen(),
      peekCard: peekCard(),
      operationMode: controls().operationMode,
    });
    if (completed.length) saveProgress(progress);
    if (shown) {
      updateShown(state, now);
      return;
    }
    const next = wanted(state);
    if (!next) {
      candidate = null;
      return;
    }
    if (!candidate || candidate.kind !== next.kind || candidate.id !== next.id) candidate = { ...next, since: now };
    if (now - candidate.since < APPEAR_MS) return;
    candidate = null;
    show(next.kind, next.id, now);
    updateShown(state, now);
  }
  dismiss.addEventListener('click', function dismissHint() {
    if (!shown) return;
    if (shown.kind === 'step') {
      progress.steps[shown.id] = true;
      if (shown.id === 'move') for (const axis of MOVES) progress.moves[axis] = true;
    }
    saveProgress(progress);
    hide();
  });
  document.addEventListener('rov-input-device', function deviceChanged(event) {
    const detail = event.detail;
    family = detail && detail !== 'touch' ? deviceFamily(detail) : 'keyboard';
    if (shown && lastState) updateShown(lastState, performance.now());
  });
  document.addEventListener(ONBOARDING_CHANGED, function reload() {
    progress = loadProgress();
    hide();
  });
  // The pause menu's 操作教學 page: every basic step with its controls, ticked when done.
  function renderTutorial(container) {
    container.replaceChildren();
    container.append(element('h3', 'bp-kicker', STRINGS.tutorial.title));
    container.append(element('p', 'menu-help', STRINGS.tutorial.intro));
    const list = element('ol', 'onboarding-tutorial');
    for (const id of STEPS) {
      const content = stepContent(id, lastState);
      const done = !!progress.steps[id];
      const row = element('li');
      row.dataset.done = String(done);
      row.append(element('strong', '', content.heading));
      for (const item of content.lines) {
        const line = element('span', 'ob-line');
        const caps = element('span', 'ob-caps');
        caps.innerHTML = item.caps;
        line.append(caps, element('span', 'ob-label', item.label));
        row.append(line);
      }
      row.append(element('small', 'ob-state', done ? STRINGS.tutorial.done : STRINGS.tutorial.open));
      list.append(row);
    }
    container.append(list);
  }
  const api = {
    update,
    renderTutorial,
    get tutorialLabel() {
      return STRINGS.tutorial.title;
    },
    // For the browser checks: what is on screen and what has been learnt.
    snapshot() {
      return { shown: shown && { ...shown }, progress: JSON.parse(JSON.stringify(progress)), family };
    },
  };
  if (!readOnly) globalThis.__onboarding = api;
  return api;
}

