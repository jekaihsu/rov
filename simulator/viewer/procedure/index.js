// Deployment checklist and post-dive log. Server owns progression and safety gates.
const STRINGS = {
  auto: '依模式（訓練完整／遊戲快速）',
  title: '潛前檢查與回收', full: '完整作業流程', quick: '快速下水',
  provisional: '上電順序、提示音、燈號：暫定，待實測。' +
    '短測為模擬診斷，每顆 2 秒；禁止拋擲。',
  checks: ['外觀、密封與穿艙件已檢查', '纜線接頭與固定環已確認', '配重與配平已確認',
    '岸上供電與載具上電已確認（暫定）', '通訊已確認', '相機影像已確認', '燈光已確認',
    '逐顆推進器短測完成', '深度零點與羅盤已確認', '入水、人員離開後才解鎖，已確認'],
  keys: ['seals', 'connector', 'trim', 'power', 'communication', 'camera', 'lights',
    'thrusters', 'instruments', 'unlock'],
  skip: '跳過未完成檢查（可能引發故障並扣分）', tender: '與纜線手確認就緒',
  lower: '選上游點，以纜線緩放入水', water: '影像、配平與功能正常；人員已離開',
  recover: '水面上鎖後收纜回收', rinse: '已以淡水沖洗', inspect: '潛後檢查完成',
  save: '儲存日誌', export: '匯出日誌', notes: '潛水註記', test: '短測推進器',
  summary: '作業紀錄：秒 / 最大深度 m / 最大纜長 m / 扣分',
  fault: '未檢項目發生故障，已扣分，必要時中止作業收纜回收。',
  dry: '離水運轉超過 30 秒，已告警並扣分。',
  recovering: '收纜中，洋流與模擬浪況會降低回收速度（暫定）', complete: '潛後處理完成',
};

export function installProcedure({send, readOnly = false}) {
  const query = new URLSearchParams(location.search);
  const training = query.get('mission') === 'scenario_training' &&
    query.get('procedure') !== 'quick';
  const preference = query.get('procedure') || localStorage.getItem('rov.procedure');
  const enabled = !readOnly && !query.has('nointro') && (preference === 'full' || training);
  let begunGeneration;
  let latest;
  let signature;
  const panel = document.createElement('section');
  panel.id = 'procedurePanel';
  panel.style.cssText = 'position:fixed;right:4%;top:12%;z-index:95;max-height:76vh;overflow:auto;' +
    'width:min(440px,90vw);padding:24px;background:rgba(8,18,26,.92);color:#e8f1f5;' +
    'border:1px solid #4fd1e0;border-radius:10px;backdrop-filter:blur(14px)';
  panel.hidden = true;
  document.body.append(panel);
  function command(action, extra = {}) {
    send({type: 'procedure', action, ...extra});
  }
  function button(text, action, extra) {
    const el = document.createElement('button');
    el.textContent = text;
    el.style.cssText = 'display:block;margin:12px 0;padding:10px;color:inherit;background:#163343';
    el.onclick = function activate() { command(action, extra); };
    panel.append(el);
    return el;
  }
  function exportLog() {
    const blob = new Blob([JSON.stringify(latest, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'dive-log.json';
    link.click();
    setTimeout(function revoke() { URL.revokeObjectURL(url); }, 1000);
  }
  function update(state) {
    if (readOnly) return;
    if (query.get('mission') === 'campaign' && !state.campaign?.chapter) return;
    if (enabled && !state.procedure?.active && begunGeneration !== state.control_generation) {
      begunGeneration = state.control_generation;
      command('begin');
    }
    const p = state.procedure;
    if (!p?.active) return;
    latest = p;
    const nextSignature = JSON.stringify([p.phase, p.checked, p.tests, p.confirmed, p.diagnostic > 0, p.penalty]);
    if (signature === nextSignature) return;
    signature = nextSignature;
    panel.hidden = false;
    panel.replaceChildren();
    const title = document.createElement('h2');
    title.textContent = STRINGS.title;
    const note = document.createElement('p');
    note.textContent = STRINGS.provisional;
    panel.append(title, note);
    const summary = document.createElement('p');
    summary.textContent = `${STRINGS.summary}：${p.elapsed} / ${p.max_depth} / ${p.max_cable} / ${p.penalty}`;
    panel.append(summary);
    if (p.dry_seconds > 30) panel.append(STRINGS.dry);
    if (p.events.some(function fault(event) { return event.action === 'fault'; })) panel.append(STRINGS.fault);
    if (p.phase === 'checks') {
      for (const i of p.checked.map(function index(key) { return STRINGS.keys.indexOf(key); })) {
        const done = document.createElement('p');
        done.textContent = '✓ ' + STRINGS.checks[i];
        panel.append(done);
      }
      if (p.checked.length === 7) {
        for (let i = 0; i < p.thrusters; i++) {
          const test = button(`${STRINGS.test} ${i + 1}`, 'test', {index: i});
          test.disabled = p.tests.includes(i) || p.diagnostic > 0;
        }
      }
      button(STRINGS.checks[p.checked.length], 'check', {key: STRINGS.keys[p.checked.length]});
      button(STRINGS.skip, 'skip');
    }
    if (p.phase === 'launch') {
      button(STRINGS.tender, 'tender').disabled = p.confirmed;
      button(STRINGS.lower, 'lower', {point: 'upstream'}).disabled = !p.confirmed;
    }
    if (p.phase === 'water_check') button(STRINGS.water, 'water_confirm');
    if (p.phase === 'diving') button(STRINGS.recover, 'recover');
    if (p.phase === 'recovering') panel.append(STRINGS.recovering);
    if (p.phase === 'post') button(STRINGS.rinse, 'rinse');
    if (p.phase === 'inspect') button(STRINGS.inspect, 'inspect');
    if (p.phase === 'log') {
      const notes = document.createElement('textarea');
      notes.placeholder = STRINGS.notes;
      notes.setAttribute('aria-label', STRINGS.notes);
      panel.append(notes);
      button(STRINGS.save, 'save').onclick = function save() { command('save', {notes: notes.value}); };
    }
    if (p.phase === 'complete') {
      panel.append(STRINGS.complete);
      button(STRINGS.export).onclick = exportLog;
    }
  }
  let held = false;
  setInterval(function navigateProcedure() {
    if (panel.hidden || !latest || latest.phase === 'diving') return;
    const pad = [...(navigator.getGamepads?.() || [])].find(function connected(value) { return value; });
    if (!pad) return;
    const down = pad.buttons[13]?.pressed || pad.axes[1] > .6;
    const up = pad.buttons[12]?.pressed || pad.axes[1] < -.6;
    const accept = pad.buttons[0]?.pressed;
    const pressed = down || up || accept;
    if (pressed && !held) {
      const buttons = [...panel.querySelectorAll('button:not(:disabled), textarea')];
      let index = buttons.indexOf(document.activeElement);
      if (accept && index >= 0) buttons[index].click();
      else {
        index = (index + (up ? -1 : 1) + buttons.length) % buttons.length;
        buttons[index]?.focus();
      }
    }
    held = pressed;
  }, 100);
  function startIntro(play) {
    if (!enabled) play();
  }
  return {update, startIntro};
}

export function installProcedureSetting(form) {
  const label = document.createElement('label');
  label.textContent = STRINGS.full;
  const select = document.createElement('select');
  select.id = 'menuProcedure';
  select.append(new Option(STRINGS.auto, 'auto'),
    new Option(STRINGS.quick, 'quick'), new Option(STRINGS.full, 'full'));
  select.value = localStorage.getItem('rov.procedure') || 'auto';
  label.append(select);
  form.append(label);
  form.addEventListener('submit', function saveSetting() {
    localStorage.setItem('rov.procedure', select.value);
  }, {capture: true});
}
