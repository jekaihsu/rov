// Course-map DOM for the internal training mode: groups, skill goals, duration,
// and provisional pass criteria from the curriculum / research report.

import {lessonsByGroup} from './catalogue.js';
import {diveUrl, listDives} from '../replay_store.js';
import {listRecords} from './records.js';
import {downloadTrainingCsv, downloadScorecardPdf} from './export.js';
import {localize} from '../i18n/index.js';

const STRINGS = localize('training.map', {
  title: '訓練模式',
  help: '內部版課程地圖。通過標準照研究報告與公司課表撰寫，門檻暫定待基準航次校準。紀錄只存本機。',
  groupIntro: '入門',
  groupOperator: '操作員',
  groupAdvanced: '進階',
  groupIncident: '事故處置',
  minutes: '{n} 分',
  goal: '目標技能',
  criteria: '通過標準',
  start: '開始練習',
  records: '本機紀錄',
  exportCsv: '匯出全部 CSV',
  exportLast: '匯出最近成績單',
  noRecords: '尚無本機紀錄',
  lastPass: '最近：暫定通過',
  lastFail: '最近：需補訓',
  steamHidden: 'Steam 版不提供訓練模式',
});

const GROUP_LABEL = {
  intro: 'groupIntro',
  operator: 'groupOperator',
  advanced: 'groupAdvanced',
  incident: 'groupIncident',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function latestFor(lessonId) {
  const records = listRecords().filter(function match(row) {
    return row.lessonId === lessonId;
  });
  return records.at(-1) || null;
}

export function buildCourseMap({catalogue, onChoose, showRecords = true} = {}) {
  const root = element('div', 'training-map');
  root.append(element('p', 'menu-help', STRINGS.help));

  if (showRecords) {
    const tools = element('div', 'training-map-tools');
    const csv = element('button', 'menu-link', STRINGS.exportCsv);
    csv.type = 'button';
    csv.onclick = function exportAll() {
      downloadTrainingCsv(listRecords());
    };
    const pdf = element('button', 'menu-link', STRINGS.exportLast);
    pdf.type = 'button';
    pdf.onclick = function exportLast() {
      const last = listRecords().at(-1);
      if (!last) {
        pdf.textContent = STRINGS.noRecords;
        return;
      }
      downloadScorecardPdf(last);
    };
    tools.append(csv, pdf);
    root.append(tools);
  }

  const available = listDives().catch(() => []);
  for (const group of lessonsByGroup(catalogue)) {
    const section = element('section', 'training-group');
    section.dataset.group = group.id;
    const labelKey = GROUP_LABEL[group.id];
    section.append(element('h3', 'training-group-title', STRINGS[labelKey] || group.id));
    const list = element('div', 'menu-card-grid training-lesson-grid');
    for (const lesson of group.lessons) {
      const card = element('article', 'menu-card training-lesson');
      card.dataset.lesson = lesson.id;
      card.append(element('h4', 'menu-card-title', lesson.title));
      const meta = element('p', 'menu-card-meta',
        STRINGS.minutes.replace('{n}', String(lesson.simulatorMinutes)));
      card.append(meta);
      card.append(element('p', 'training-goal', `${STRINGS.goal}：${lesson.goal}`));
      card.append(element('p', 'training-criteria', `${STRINGS.criteria}：${lesson.criteria}`));
      const latest = latestFor(lesson.id);
      if (latest) {
        card.append(element('p', 'training-record',
          latest.passProvisional ? STRINGS.lastPass : STRINGS.lastFail));
      }
      if (latest?.replayId) available.then(ids => {
        if (!ids.includes(latest.replayId)) return;
        const replay = element('a', 'menu-link', '▶');
        replay.href = diveUrl(latest.replayId);
        replay.setAttribute('aria-label', latest.lessonTitle + ' ▶');
        card.append(replay);
      });
      const start = element('button', 'menu-primary', STRINGS.start);
      start.type = 'button';
      start.onclick = function choose() {
        onChoose?.(lesson);
      };
      card.append(start);
      list.append(card);
    }
    section.append(list);
    root.append(section);
  }
  return root;
}
