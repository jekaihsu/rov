// In-game pause menu (Esc, or hold Start; both from the `pause` row of input/bindings.js): resume, restart
// (host, confirmed with a second press), settings and back to the launch menu, beside a summary of the current
// objective and, in the expedition sea, the contracts on offer (play/contracts.js). While it is open the input
// layer is blocked, so the pilot's own sticks are centred and held buttons released. A solo host also pauses the simulation; in a shared room the simulation
// keeps running for everyone else. Settings reuse the launch menu's tabs over the in-game controls.
import { createMenuNavigator, loadControllerDatabase, renderPrompts } from './navigator.js';
import { acceptContract, contractBoard } from '../play/contracts.js';
import { objectiveSummary } from '../play/mission_text.js';
import { restartRun } from '../play/restart.js';
import { mountDisplaySettings } from './display_settings.js';
import { fitTitle, primaryButton } from './big_picture.js';
import {
  createSettingsPanel,
  element,
  mountAudio,
  mountChoices,
  mountFidelity,
  mountKeyHints,
  mountToggles,
} from './settings.js';

import { localize } from '../i18n/index.js';
import {
  canOpenReportsFolder,
  openFeedbackReport,
  openReportsFolder,
} from '../feedback/index.js';

const STRINGS = localize('menu.pause', {
  title: '暫停',
  resume: '繼續',
  restart: '重新開始',
  restartConfirm: '再按一次確認重新開始',
  restartHost: '只有房主可以重新開始。',
  objective: '目前目標',
  contracts: '工程委託',
  accept: '接取：{label}',
  settings: '設定',
  report: '回報問題',
  openReports: '開啟回報資料夾',
  home: '返回主選單',
  // [short line on the screen, full explanation as its tooltip]
  solo: ['模擬已暫停 · 繼續後先回中再解鎖', '單人潛航：模擬已暫停。繼續後請先回中、再解鎖。'],
  shared: ['多人房間 · 模擬持續進行', '多人房間：模擬持續進行，你的操控已回中；其他人照常駕駛。'],
  replay: ['回放中 · 關閉選單即可繼續', '回放中：關閉選單即可繼續。'],
  tabs: {
    fidelity: '擬真設定', controls: '控制', audio: '音訊', quality: '畫質', display: '顯示', interface: '介面',
  },
  controller: '開啟手把設定（死區、曲線、綁定）',
  quality: {
    auto: ['自動', '目標 60 FPS'],
    performance: ['流暢', '降低解析度'],
    medium: ['標準', '原生解析度'],
    high: ['高', '細節優先'],
  },
  interface: {
    optFog: ['真實能見度', '關閉後水體較清澈，超出真機影像。'],
    optFlow: ['洋流粒子', '水中懸浮粒子隨洋流移動。'],
    optLabels: ['場景標籤', '在結構物旁顯示名稱。'],
    optSticks: ['畫面搖桿', '只在觸控裝置上顯示。'],
    optPip: ['操作員小視窗', '在畫面角落顯示岸上操作員。'],
  },
  prompts: { move: '移動', accept: '確認', back: '返回', tabs: '分頁' },
});

// While the menu is up the flight instruments are hidden, so the paused scene behind it is clean (big_picture.css).
const OPEN_CLASS = 'pause-open';

let open = false;

export function pauseMenuOpen() {
  return open;
}

function byId(id) {
  return document.getElementById(id);
}

function introPlaying() {
  const skip = byId('skipIntro');
  return !!skip && !skip.hidden;
}

function isHost(state) {
  const room = state?.room;
  if (!room) return true;
  const host = room.players?.find(function hostPlayer(player) {
    return player.id === room.host_id;
  });
  return host?.vehicle_id === state.vehicle_id;
}

function solo(state) {
  const pilots = state?.room?.players?.filter(function connected(player) {
    return player.connected;
  }).length ?? state?.vehicles?.length ?? 1;
  return pilots <= 1;
}

// Proxy a pause-menu control onto the drawer control that already owns the behaviour.
function drive(id, value) {
  const target = byId(id);
  if (!target) return;
  if (target.type === 'checkbox') target.checked = value;
  else target.value = value;
  target.dispatchEvent(new Event('input', { bubbles: true }));
  target.dispatchEvent(new Event('change', { bubbles: true }));
}

function buildSettings(input) {
  return createSettingsPanel({
    idPrefix: 'pauseSettings',
    tabs: [
      { id: 'fidelity', label: STRINGS.tabs.fidelity, mount: mountFidelity },
      {
        id: 'controls',
        label: STRINGS.tabs.controls,
        mount(pane) {
          const opener = element('button', 'menu-next menu-wide', STRINGS.controller);
          opener.type = 'button';
          opener.addEventListener('click', function openController() {
            byId('inputSettingsButton')?.click();
          });
          pane.append(opener);
          const state = input.hudState();
          mountKeyHints(pane, state.bindings, { rows: state.keyRows, operationMode: state.operationMode });
        },
      },
      { id: 'audio', label: STRINGS.tabs.audio, mount: mountAudio },
      {
        id: 'quality',
        label: STRINGS.tabs.quality,
        mount(pane) {
          mountChoices(pane, {
            name: 'quality',
            options: Object.entries(STRINGS.quality).map(function option([value, [label, detail]]) {
              return [value, label, detail];
            }),
            value: byId('quality')?.value || 'auto',
            onChange(value) {
              drive('quality', value);
            },
          });
        },
      },
      { id: 'display', label: STRINGS.tabs.display, mount: mountDisplaySettings },
      {
        id: 'interface',
        label: STRINGS.tabs.interface,
        mount(pane) {
          mountToggles(pane, Object.entries(STRINGS.interface).filter(function present([id]) {
            return !!byId(id);
          }).map(function toggle([id, [label, help]]) {
            return {
              id: `pause-${id}`,
              label,
              help,
              checked: byId(id).checked,
              onChange(value) {
                drive(id, value);
              },
            };
          }));
        },
      },
    ],
  });
}

// input: the object installInput returned; send: app's socket sender; state(): latest server state.
// extraActions(): optional [{id, label, run, keepOpen, disabled, title}] shown with the objective (the YX work
// order's confirmations and early hand-in from career/dive.js, recovery during a dive from procedure/index.js), so
// a pad player reaches them without the mouse. A disabled entry shows its title as the reason.
export function installPauseMenu({ input, send, state, replay = false, extraActions = null }) {
  const root = element('section', 'pause-menu');
  root.id = 'pauseMenu';
  root.hidden = true;
  root.setAttribute('role', 'dialog');
  root.setAttribute('aria-modal', 'true');
  root.setAttribute('aria-label', STRINGS.title);
  const side = element('div', 'pause-side');
  // Big-picture layout (big_picture.js): one status line, a large title, 繼續 as the primary button.
  const note = element('p', 'bp-kicker');
  const heading = element('h2', 'bp-title');
  fitTitle(heading, STRINGS.title);
  const list = element('nav', 'menu-list');
  const objective = element('section', 'pause-objective');
  objective.id = 'pauseObjective';
  const objectiveLines = element('ul', 'pause-objective-lines');
  const offers = element('div', 'pause-offers');
  objective.append(element('h3', 'bp-kicker', STRINGS.objective), objectiveLines, offers);
  const main = element('div', 'pause-main');
  const footer = element('footer', 'pause-footer');
  side.append(note, heading, list, objective);
  root.append(side, main, footer);
  document.body.append(root);
  let settings = null;
  let view = 'list';
  let pausedByMenu = false;
  let navigator = null;
  let restartArmed = false;
  function entry(id, label, handler) {
    const button = element('button', 'menu-entry');
    button.type = 'button';
    button.id = id;
    button.append(element('span', 'menu-entry-label', label));
    button.addEventListener('click', handler);
    list.append(button);
    return button;
  }
  function prompts() {
    const items = [['navigate', STRINGS.prompts.move], ['accept', STRINGS.prompts.accept]];
    if (view === 'settings') items.push([['tabPrevious', 'tabNext'], STRINGS.prompts.tabs]);
    items.push(['back', STRINGS.prompts.back]);
    renderPrompts(footer, items, navigator?.family || 'keyboard');
    settings?.setFamily(navigator?.family || 'keyboard');
  }
  function showList() {
    view = 'list';
    main.hidden = true;
    prompts();
    resume.focus({ preventScroll: true });
  }
  function host(current) {
    return isHost(current) && !replay;
  }
  // The objective summary and, in the expedition sea, contracts the host can accept with the pad.
  function renderObjective() {
    const current = state();
    const lines = current ? objectiveSummary(current) : [];
    objectiveLines.replaceChildren(...lines.map(function line(text) {
      return element('li', '', text);
    }));
    objective.hidden = !lines.length;
    offers.replaceChildren();
    const board = replay ? null : contractBoard(current, host(current));
    for (const offer of board?.offers || []) {
      const button = element('button', 'menu-chip menu-chip-small', STRINGS.accept.replace('{label}', offer.label));
      button.type = 'button';
      button.dataset.contract = offer.kind;
      button.disabled = !offer.enabled;
      button.title = offer.reason || offer.help;
      button.addEventListener('click', function accept() {
        const error = acceptContract(send, offer.kind);
        if (error) note.textContent = error;
        else hide();
      });
      offers.append(button);
    }
    for (const action of replay ? [] : extraActions?.() || []) {
      const button = element('button', 'menu-chip menu-chip-small', action.label);
      button.type = 'button';
      button.dataset.action = action.id;
      button.disabled = !!action.disabled;
      if (action.title) button.title = action.title;
      button.addEventListener('click', function runAction() {
        action.run();
        if (!action.keepOpen) {
          hide();
          return;
        }
        renderObjective();
        offers.querySelector(`[data-action="${action.id}"]`)?.focus({ preventScroll: true });
      });
      offers.append(button);
    }
    objective.hidden = objective.hidden && !offers.children.length;
  }
  function renderRestart() {
    const current = state();
    restart.disabled = replay || !host(current);
    restart.title = restart.disabled && !replay ? STRINGS.restartHost : '';
    restartArmed = false;
    restartLabel.textContent = STRINGS.restart;
  }
  function showSettings() {
    if (!settings) {
      settings = buildSettings(input);
      main.append(settings.element);
    }
    view = 'settings';
    main.hidden = false;
    prompts();
    requestAnimationFrame(function focusTabs() {
      navigator?.focusFirst(main);
    });
  }
  function release() {
    input.keys.clear();
    input.hold.photo.clear();
    input.hold.record.clear();
    for (const channel of Object.keys(input.touch)) input.touch[channel] = 0;
    for (const channel of Object.keys(input.out)) input.out[channel] = 0;
  }
  function show() {
    if (open) return;
    open = true;
    release();
    const current = state();
    let message = STRINGS.shared;
    if (replay) message = STRINGS.replay;
    else if (current && solo(current) && isHost(current) && !current.controller) {
      message = STRINGS.solo;
      if (!current.paused) pausedByMenu = send({ type: 'pause', value: true });
    }
    [note.textContent, note.title] = message;
    renderObjective();
    renderRestart();
    root.hidden = false;
    document.body.classList.add(OPEN_CLASS);
    navigator?.setActive(true);
    navigator?.start();
    showList();
  }
  function hide() {
    if (!open) return;
    open = false;
    root.hidden = true;
    document.body.classList.remove(OPEN_CLASS);
    navigator?.setActive(false);
    navigator?.stop();
    if (pausedByMenu) send({ type: 'pause', value: false });
    pausedByMenu = false;
  }
  const { button: resume } = primaryButton('pauseResume', STRINGS.resume, { cap: false });
  resume.addEventListener('click', hide);
  list.append(resume);
  const restart = entry('pauseRestart', STRINGS.restart, function restartPressed() {
    if (!restartArmed) {
      restartArmed = true;
      restartLabel.textContent = STRINGS.restartConfirm;
      return;
    }
    const current = state();
    hide();
    restartRun(send, current);
  });
  const restartLabel = restart.querySelector('.menu-entry-label');
  restart.addEventListener('blur', function disarm() {
    restartArmed = false;
    restartLabel.textContent = STRINGS.restart;
  });
  entry('pauseSettings', STRINGS.settings, showSettings);
  entry('pauseReport', STRINGS.report, function report() {
    openFeedbackReport();
  });
  if (canOpenReportsFolder()) {
    entry('pauseReportsFolder', STRINGS.openReports, function openFolder() {
      openReportsFolder().catch(function failed(error) {
        note.textContent = error?.message || STRINGS.openReports;
      });
    });
  }
  entry('pauseHome', STRINGS.home, function home() {
    hide();
    byId('returnMenu')?.click();
  });
  main.hidden = true;
  input.registerActions({
    pause: {
      run() {
        if (open) hide();
        else show();
      },
      enabled() {
        return !introPlaying();
      },
    },
  });
  loadControllerDatabase().then(function ready(database) {
    navigator = createMenuNavigator({
      database,
      handlers: {
        scope() {
          return view === 'settings' ? main : side;
        },
        back() {
          if (view === 'settings') showList();
          else hide();
        },
        tab(direction) {
          if (view === 'settings') settings.step(direction);
        },
        family: prompts,
      },
    });
  });
  return {
    show,
    hide,
    get open() {
      return open;
    },
  };
}
