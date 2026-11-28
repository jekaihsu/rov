// Local survey log for the cable worksite, available in the mission drawer during a dive.
import {localize} from '../i18n/index.js';

const STRINGS = localize('story.repair_report', {
  scale: '比例依據：工單鎧裝外徑', fix: '甲板回報定位失準', title: '修纜現場紀錄', shore_end: '岸側斷面', sea_end: '海側斷面', housing: '不明物外觀',
  relative: '相對岩面 ΔN/E/D（m）', gap: '兩斷面直線距離', position: '北／東／深度（m）', empty: '尚無觀測照片',
});

let panel;
let body;
let last;

export function repairReportLines(report) {
  const rows = Object.entries(report.observations);
  const lines = rows.map(function formatObservation([id, row]) {
    const label = row.from_rock_ned_m ? STRINGS.relative : STRINGS.position;
    const position = row.from_rock_ned_m || row.pos_ned_m;
    return `${STRINGS[id]} · ${row.photo} · T+${row.t} s · ${row.depth_m} m · ${label} ${position.join(' / ')}`;
  });
  if (!lines.length) lines.push(STRINGS.empty);
  const reference = rows.find(([, row]) => row.reference_od_m);
  if (reference) lines.push(`${STRINGS.scale} ${reference[1].reference_od_m * 100} cm`);
  if (report.deck_fix_interval_s) lines.push(`${STRINGS.fix} · T+${report.deck_fix_interval_s.join(' – ')} s`);
  if (report.end_separation_m != null) lines.push(`${STRINGS.gap} ${report.end_separation_m} m`);
  return lines;
}

export function updateRepairReport(report) {
  if (!report) {
    if (panel) panel.hidden = true;
    return;
  }
  if (!panel) {
    panel = document.createElement('details');
    const title = document.createElement('summary');
    title.textContent = STRINGS.title;
    body = document.createElement('div');
    panel.append(title, body);
    document.querySelector('.mission-tools').append(panel);
  }
  panel.hidden = false;
  const lines = repairReportLines(report);
  const signature = lines.join('\n');
  if (signature === last) return;
  last = signature;
  body.replaceChildren(...lines.map(function paragraph(line) {
    const text = document.createElement('p');
    text.textContent = line;
    return text;
  }));
}
