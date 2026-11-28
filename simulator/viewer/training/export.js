// Local CSV and one-page printable HTML scorecard (browser print-to-PDF), matching
// the debrief/HTML pattern in PROTOCOL.md. Nothing is uploaded.

import {recordsToCsv} from './scorecard.js';
import {localize} from '../i18n/index.js';

const STRINGS = localize('training.export', {
  title: '學員成績單',
  subtitle: '內部訓練 · 僅存本機',
  provisional: '合格門檻暫定，待資深操作員基準航次校準。不上傳。',
  student: '學員',
  lesson: '課程',
  level: '等級',
  elapsed: '時間（秒）',
  contacts: '纜線接觸次數',
  tension: '最大張力（N）',
  collisions: '碰撞',
  photos: '照片',
  photoQuality: '照片品質（暫定）',
  procedure: '程序照順序',
  fidelity: '擬真設定',
  assist: '輔助使用',
  result: '結果',
  pass: '暫定通過',
  fail: '需補訓／證據不足',
  criteria: '通過標準',
  goal: '目標技能',
  yes: '是',
  no: '否',
  severe: '嚴重',
});

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function downloadBlob(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(function revoke() {
    URL.revokeObjectURL(url);
  }, 1000);
}

function documentLang() {
  return globalThis.document?.documentElement?.lang || 'zh-Hant';
}

export function downloadTrainingCsv(records, filename = 'training-records.csv') {
  downloadBlob(filename, recordsToCsv(records), 'text/csv;charset=utf-8');
}

export function buildScorecardHtml(scorecard, strings = {}) {
  const s = {...STRINGS, ...strings};
  const passLabel = scorecard.passProvisional ? s.pass : s.fail;
  const photoDetail = scorecard.photoMeanStandoffM != null
    ? `${scorecard.photos} · ${scorecard.photoQuality} · ${scorecard.photoMeanStandoffM} m`
    : `${scorecard.photos} · ${scorecard.photoQuality}`;
  const fidelityDetail = [
    scorecard.fidelityPreset,
    scorecard.fidelityLeftReal ? 'left_real' : 'stayed_real',
  ].join(' / ');
  return `<!doctype html>
<html lang="${escapeHtml(documentLang())}">
<head>
<meta charset="utf-8">
<title>${escapeHtml(s.title)}</title>
<style>
@page{size:A4 portrait;margin:14mm}
body{font:13px/1.45 system-ui,sans-serif;color:#102018;margin:0}
h1{font-size:22px;margin:0 0 4px}
.eyebrow{letter-spacing:.1em;text-transform:uppercase;color:#4a6a58;font-size:11px}
.meta{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0}
.meta div{border:1px solid #c5d5cb;padding:8px 10px;background:#fff}
.meta strong{display:block;font-size:16px}
table{border-collapse:collapse;width:100%;margin-top:8px}
th,td{border:1px solid #c5d5cb;padding:6px 8px;text-align:left}
th{background:#e4eee7;width:38%}
.note{margin-top:10px;font-size:11px;color:#3a4a40}
@media print{body{margin:0}}
</style>
</head>
<body>
<p class="eyebrow">${escapeHtml(s.subtitle)}</p>
<h1>${escapeHtml(s.title)}</h1>
<p>${escapeHtml(s.provisional)}</p>
<section class="meta">
  <div><span>${escapeHtml(s.student)}</span><strong>${escapeHtml(scorecard.student || '—')}</strong></div>
  <div><span>${escapeHtml(s.lesson)}</span><strong>${escapeHtml(scorecard.lessonTitle || scorecard.lessonId)}</strong></div>
  <div><span>${escapeHtml(s.level)}</span><strong>${escapeHtml(scorecard.level || '—')}</strong></div>
  <div><span>${escapeHtml(s.result)}</span><strong>${escapeHtml(passLabel)}</strong></div>
</section>
<p><strong>${escapeHtml(s.goal)}</strong>：${escapeHtml(scorecard.goal || '—')}</p>
<p><strong>${escapeHtml(s.criteria)}</strong>：${escapeHtml(scorecard.criteria || scorecard.passStatus || '—')}</p>
<table>
<tbody>
<tr><th>${escapeHtml(s.elapsed)}</th><td>${escapeHtml(scorecard.elapsedS)}</td></tr>
<tr><th>${escapeHtml(s.contacts)}</th><td>${escapeHtml(scorecard.tetherContactEpisodes)}</td></tr>
<tr><th>${escapeHtml(s.tension)}</th><td>${escapeHtml(scorecard.maxTensionN)}</td></tr>
<tr><th>${escapeHtml(s.collisions)}</th>
<td>${escapeHtml(scorecard.collisions)} / ${escapeHtml(s.severe)} ${escapeHtml(scorecard.severeCollisions)}</td></tr>
<tr><th>${escapeHtml(s.photos)}</th><td>${escapeHtml(photoDetail)}</td></tr>
<tr><th>${escapeHtml(s.procedure)}</th>
<td>${escapeHtml(scorecard.procedureInOrder ? s.yes : s.no)}</td></tr>
<tr><th>${escapeHtml(s.fidelity)}</th><td>${escapeHtml(fidelityDetail)}</td></tr>
<tr><th>${escapeHtml(s.assist)}</th>
<td>${escapeHtml(scorecard.assistedUsed ? s.yes : s.no)}</td></tr>
</tbody>
</table>
<p class="note">${escapeHtml(scorecard.passStatus || '')}</p>
</body>
</html>`;
}

export function downloadScorecardPdf(scorecard, strings = {}, filename = 'training-scorecard.html') {
  // One-page HTML for browser print-to-PDF (same approach as debrief reports).
  downloadBlob(filename, buildScorecardHtml(scorecard, strings), 'text/html;charset=utf-8');
}

export function printScorecard(scorecard, strings = {}) {
  const html = buildScorecardHtml(scorecard, strings);
  const popup = window.open('', '_blank', 'noopener,noreferrer,width=900,height=1200');
  if (!popup) {
    downloadScorecardPdf(scorecard, strings);
    return;
  }
  popup.document.open();
  popup.document.write(html);
  popup.document.close();
  popup.focus();
  setTimeout(function doPrint() {
    popup.print();
  }, 250);
}
