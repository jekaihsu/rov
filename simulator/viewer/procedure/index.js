// Deployment checklist, tended launch, recovery and post-dive log panel. The server owns progression and safety
// gates (qysim/procedure.py); this module only renders the current phase and sends the operator's confirmations.
// Whether the full procedure runs is the `deployProcedure` fidelity item (real: full, assisted: quick); `?nointro`
// always skips it. Gamepad navigation uses the menu-context rows of input/bindings.js while the panel is open.
import {getFidelity} from '../fidelity.js';
import {PROCEDURE_ITEM} from './fidelity_item.js';

const STRINGS = {
  title: '潛前檢查與回收',
  provisional: '上電順序、提示音、燈號：暫定，待實測。' +
    '短測為模擬診斷，每顆 2 秒；禁止拋擲。',
  checks: ['外觀、密封與穿艙件已檢查', '纜線接頭與固定環已確認', '配重與配平已確認',
    '岸上供電與載具上電已確認（暫定）', '通訊已確認', '相機影像已確認', '燈光已確認',
    '逐顆推進器短測完成', '深度零點與羅盤已確認', '入水、人員離開後才解鎖，已確認'],
  keys: ['seals', 'connector', 'trim', 'power', 'communication', 'camera', 'lights',
    'thrusters', 'instruments', 'unlock'],
  skip: '跳過未完成檢查（可能引發故障並扣分）',
  tender: '與纜線手確認就緒',
  lower: '選上游點，以纜線緩放入水',
  water: '影像、配平與功能正常；人員已離開',
  recover: '水面上鎖後收纜回收',
  rinse: '已以淡水沖洗',
  inspect: '潛後檢查完成',
  save: '儲存日誌',
  export: '匯出日誌',
  notes: '潛水註記',
  test: '短測推進器',
  summary: '作業紀錄：秒 / 最大深度 m / 最大纜長 m / 扣分',
  fault: '未檢項目發生故障，已扣分，必要時中止作業收纜回收。',
  dry: '離水運轉超過 30 秒，已告警並扣分。',
  recovering: '收纜中，洋流與模擬浪況會降低回收速度（暫定）',
  complete: '潛後處理完成',
};
const STYLE = `
  #procedurePanel{position:fixed;right:4%;top:12%;z-index:var(--z-controls);max-height:76vh;overflow:auto;
    width:min(440px,90vw);box-sizing:border-box;padding:24px;background:rgba(8,18,26,.92);color:#e8f1f5;
    border:1px solid #4fd1e0;border-radius:10px;backdrop-filter:blur(14px)}
  #procedurePanel[hidden]{display:none}
  #procedurePanel button{display:block;margin:12px 0;padding:10px;color:inherit;background:#163343}
  #procedurePanel button:focus-visible{outline:2px solid #4fd1e0}
  #procedurePanel textarea{width:100%;min-height:72px}
`;

function installStyle() {
  const style = document.createElement('style');
  style.textContent = STYLE;
  document.head.append(style);
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

export function installProcedure({send, readOnly = false}) {
  const query = new URLSearchParams(location.search);
  const fidelity = getFidelity();
  let begunGeneration;
  let latest;
  let signature;
  installStyle();
  const panel = document.createElement('section');
  panel.id = 'procedurePanel';
  panel.hidden = true;
  document.body.append(panel);
  function wanted() {
    return !readOnly && !query.has('nointro') && fidelity.get(PROCEDURE_ITEM) === 'full';
  }
  function command(action, extra = {}) {
    send({type: 'procedure', action, ...extra});
  }
  function button(text, action, extra) {
    const element = document.createElement('button');
    element.type = 'button';
    element.textContent = text;
    element.onclick = function activate() {
      command(action, extra);
    };
    panel.append(element);
    return element;
  }
  function renderChecks(p) {
    for (const key of p.checked) {
      const done = document.createElement('p');
      done.textContent = '✓ ' + STRINGS.checks[STRINGS.keys.indexOf(key)];
      panel.append(done);
    }
    if (p.checked.length === 7) {
      for (let index = 0; index < p.thrusters; index++) {
        const test = button(`${STRINGS.test} ${index + 1}`, 'test', {index});
        test.disabled = p.tests.includes(index) || p.diagnostic > 0;
      }
    }
    button(STRINGS.checks[p.checked.length], 'check', {key: STRINGS.keys[p.checked.length]});
    button(STRINGS.skip, 'skip');
  }
  function renderLog() {
    const notes = document.createElement('textarea');
    notes.placeholder = STRINGS.notes;
    notes.setAttribute('aria-label', STRINGS.notes);
    panel.append(notes);
    button(STRINGS.save, 'save').onclick = function save() {
      command('save', {notes: notes.value});
    };
  }
  function renderPhase(p) {
    if (p.phase === 'checks') renderChecks(p);
    if (p.phase === 'launch') {
      button(STRINGS.tender, 'tender').disabled = p.confirmed;
      button(STRINGS.lower, 'lower', {point: 'upstream'}).disabled = !p.confirmed;
    }
    if (p.phase === 'water_check') button(STRINGS.water, 'water_confirm');
    if (p.phase === 'diving') button(STRINGS.recover, 'recover');
    if (p.phase === 'recovering') panel.append(STRINGS.recovering);
    if (p.phase === 'post') button(STRINGS.rinse, 'rinse');
    if (p.phase === 'inspect') button(STRINGS.inspect, 'inspect');
    if (p.phase === 'log') renderLog();
    if (p.phase === 'complete') {
      panel.append(STRINGS.complete);
      button(STRINGS.export).onclick = function exportLog() {
        downloadJson(latest, 'dive-log.json');
      };
    }
  }
  function render(p) {
    panel.hidden = false;
    panel.replaceChildren();
    const title = document.createElement('h2');
    title.textContent = STRINGS.title;
    const note = document.createElement('p');
    note.textContent = STRINGS.provisional;
    const summary = document.createElement('p');
    summary.textContent = `${STRINGS.summary}：${p.elapsed} / ${p.max_depth} / ${p.max_cable} / ${p.penalty}`;
    panel.append(title, note, summary);
    if (p.dry_seconds > 30) panel.append(STRINGS.dry);
    if (p.events.some(function fault(event) {
      return event.action === 'fault';
    })) panel.append(STRINGS.fault);
    renderPhase(p);
  }
  // The setting is read when a scenario (re)loads, so changing it mid-dive never teleports the vehicle.
  function update(state) {
    if (readOnly) return;
    if (query.get('mission') === 'campaign' && !state.campaign?.chapter) return;
    if (begunGeneration !== state.control_generation) {
      begunGeneration = state.control_generation;
      if (wanted() && !state.procedure?.active) command('begin');
    }
    const p = state.procedure;
    if (!p?.active) {
      panel.hidden = true;
      return;
    }
    latest = p;
    const nextSignature = JSON.stringify([p.phase, p.checked, p.tests, p.confirmed, p.diagnostic > 0, p.penalty]);
    if (signature === nextSignature) return;
    signature = nextSignature;
    render(p);
  }
  function navigable() {
    return !panel.hidden && latest && latest.phase !== 'diving';
  }
  function focusables() {
    return [...panel.querySelectorAll('button:not(:disabled), textarea')];
  }
  function moveFocus(step) {
    const items = focusables();
    if (!items.length) return;
    const index = items.indexOf(document.activeElement);
    items[(index + step + items.length) % items.length].focus();
  }
  // Menu-context rows (input/bindings.js) own the pad while the checklist is open; flight is locked on deck anyway.
  function bindInput(input) {
    input.registerActions({
      menuUp: {enabled: navigable, run: function previous() {
        moveFocus(-1);
      }},
      menuDown: {enabled: navigable, run: function next() {
        moveFocus(1);
      }},
      accept: {enabled: navigable, run: function activate() {
        const items = focusables();
        if (items.includes(document.activeElement)) document.activeElement.click();
        else moveFocus(1);
      }},
    });
  }
  function startIntro(play) {
    if (!wanted()) play();
  }
  return {update, startIntro, bindInput};
}
