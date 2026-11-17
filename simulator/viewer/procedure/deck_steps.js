// Column content of the deck pre-dive check (procedure/index.js renders it in the lower-left column): one step at
// a time, one orange primary action, a text link only where the step offers a second choice (report a defect,
// skip). The scene reacts to each step (deck_stage.js); routine items come from the crew radio (crew_radio.js).
import {currentStation, deckStep, defectPending, nextThruster} from './deck_flow.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('procedure.deck_steps', {
  kicker: '潛前檢查',
  launchKicker: '下水',
  titles: {walkaround: '繞機目視檢查', power: '載具上電', thrusters: '推進器短測', lights: '燈光測試',
    camera: '機載影像'},
  notes: {
    walkaround: '斷電狀態下繞載具一圈，逐處看密封、接頭與推進器護罩。看到不對就回報。',
    power: '開岸電、載具上電。看狀態燈，聽開機提示音。',
    thrusters: '人員離開推進器。每顆短測 2 秒，空氣中累計不超過 30 秒。',
    lights: '開燈，確認兩盞都亮、照到甲板，看完就關；燈在空氣中不宜久開。',
    camera: '畫面已切到機載鏡頭：確認有影像、對焦清楚、時間在走。',
  },
  stations: ['前方 · 鏡頭罩與燈', '左舷 · 推進器與護罩', '上方 · 艙體密封', '後方 · 纜線接頭',
    '右舷 · 推進器與護罩'],
  lookFor: ['鏡頭罩與燈罩有沒有裂痕或髒污。', '推進器有沒有纏繞物，護罩有沒有裂痕。',
    '端蓋密封面、O 形環上有沒有沙或毛髮。', '纜線接頭的固定環是否鎖到底。', '推進器有沒有纏繞物，護罩有沒有裂痕。'],
  startWalk: '開始繞機',
  next: '下一處',
  doneWalk: '繞機完成',
  report: '這裡有異常',
  station: '{n} / {total}',
  defects: {line_fouled: '推進器護罩上掛著一段繩子', guard_cracked: '推進器護罩裂了',
    oring_debris: '密封面上有沙和毛髮', connector_unlocked: '纜線接頭固定環沒鎖到底'},
  fixes: {line_fouled: '剪掉繩子，清乾淨護罩。', guard_cracked: '換上備用護罩。',
    oring_debris: '拆開端蓋，清潔 O 形環、重新上油。', connector_unlocked: '把固定環轉到底鎖上。'},
  foundKicker: '發現異常',
  fix: '排除',
  fixing: '處理中…',
  fixed: '已排除：{what}',
  powerOn: '上電',
  booting: '開機中…',
  pulse: '短測 T{n}',
  pulsing: 'T{n} 運轉中…',
  pulsed: '{done} / {total} {unit}',
  thrusterOne: '顆',
  thrusterMany: '顆',
  lampsOn: '開燈',
  lampsLit: '兩盞都亮，關燈',
  feedOk: '影像正常',
  lower: '緩放入水',
  waitTender: '等纜線手回報纜線就緒。',
  waitTenderAction: '等待纜線手',
  lowerNote: '選上游下水點，以吊放索緩放；入水、人員離開後才解鎖。',
  skip: '跳過剩下的檢查（扣分，未發現的異常會帶下水）',
});

function fill(template, values) {
  return template.replace(/\{(\w+)\}/g, function value(_, key) {
    return String(values[key] ?? '');
  });
}

function walkaround(p, ui) {
  const station = currentStation(p);
  const total = p.stations.length;
  const defect = p.defect;
  if (defectPending(p)) {
    const parts = ui.header(STRINGS.foundKicker, STRINGS.stations[defect.station], STRINGS.defects[defect.kind]);
    parts.push(ui.note(STRINGS.fixes[defect.kind]));
    const fix = ui.primary(p.fix > 0 ? STRINGS.fixing : STRINGS.fix, 'fix');
    fix.disabled = p.fix > 0;
    parts.push(fix);
    return parts;
  }
  if (station < 0) {
    const parts = ui.header(STRINGS.kicker, ui.count(p), STRINGS.titles.walkaround);
    parts.push(ui.note(STRINGS.notes.walkaround), ui.primary(STRINGS.startWalk, 'look', {station: 0}));
    return parts;
  }
  const count = fill(STRINGS.station, {n: station + 1, total});
  const parts = ui.header(`${STRINGS.titles.walkaround} · ${count}`, ui.count(p), STRINGS.stations[station]);
  parts.push(ui.note(STRINGS.lookFor[station]));
  if (defect?.fixed && defect.station === station) {
    parts.push(ui.note(fill(STRINGS.fixed, {what: STRINGS.defects[defect.kind]})));
  }
  const last = station + 1 >= total;
  parts.push(last ? ui.primary(STRINGS.doneWalk, 'check', {key: 'walkaround'})
    : ui.primary(STRINGS.next, 'look', {station: station + 1}));
  const report = ui.link(STRINGS.report, 'report', function reportHere() {
    ui.command('report', {station});
  });
  report.id = 'procedureReport';
  parts.push(report);
  return parts;
}

function thrusters(p, ui) {
  const running = p.diagnostic > 0;
  const index = running ? p.diagnostic_index : nextThruster(p);
  const parts = ui.header(STRINGS.kicker, ui.count(p), STRINGS.titles.thrusters);
  const thrusterUnit = Number(p.thrusters) === 1 ? STRINGS.thrusterOne : STRINGS.thrusterMany;
  parts.push(ui.note(STRINGS.notes.thrusters),
    ui.note(fill(STRINGS.pulsed, {done: p.tests.length, total: p.thrusters, unit: thrusterUnit})));
  const label = running ? STRINGS.pulsing : STRINGS.pulse;
  const pulse = ui.primary(fill(label, {n: (index ?? 0) + 1}), 'test', {index: Math.max(0, index)});
  pulse.disabled = running || index < 0;
  parts.push(pulse);
  return parts;
}

/** Column parts of the deck flow's checks phase. ``ui`` holds index.js's builders and command(). */
export function renderDeckChecks(p, ui) {
  const step = deckStep(p);
  let parts;
  if (step === 'walkaround') parts = walkaround(p, ui);
  else if (step === 'thrusters') parts = thrusters(p, ui);
  else {
    parts = ui.header(STRINGS.kicker, ui.count(p), STRINGS.titles[step] || '');
    parts.push(ui.note(STRINGS.notes[step] || ''));
    if (step === 'power') {
      const power = ui.primary(p.powered ? STRINGS.booting : STRINGS.powerOn, 'check', {key: 'power'});
      power.disabled = !!p.powered;
      parts.push(power);
    }
    if (step === 'lights') {
      parts.push(ui.primary(p.lamps ? STRINGS.lampsLit : STRINGS.lampsOn, 'check', {key: 'lights'}));
    }
    if (step === 'camera') parts.push(ui.primary(STRINGS.feedOk, 'check', {key: 'camera'}));
  }
  parts.push(...ui.warnings(p), ui.link(STRINGS.skip, 'skip', function skip() {
    ui.command('skip');
  }));
  return parts;
}

/** Column parts of the deck flow's launch phase: the tender reports ready by radio, then one lowering action. */
export function renderDeckLaunch(p, ui) {
  const parts = ui.header(STRINGS.launchKicker, '', STRINGS.lower);
  parts.push(ui.note(p.confirmed ? STRINGS.lowerNote : STRINGS.waitTender), ...ui.warnings(p));
  const lower = ui.primary(p.confirmed ? STRINGS.lower : STRINGS.waitTenderAction, 'lower', {point: 'upstream'});
  lower.disabled = !p.confirmed;
  parts.push(lower);
  return parts;
}

/** Re-render key of the deck flow: everything the column shows. */
export function deckSignature(p) {
  return [p.seen, p.defect, p.fix > 0, !!p.lamps, p.powered, p.boot > 0, p.diagnostic_index ?? null];
}
