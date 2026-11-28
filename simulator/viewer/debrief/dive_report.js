// Internal review sheet. Build with DOM text nodes so imported labels remain plain text in local exports.
import {createDiveRecord, channels, findings} from './dive_record.js';
import {drawPlots} from './dive_plots.js';
import {STRINGS as S} from './dive_strings.js';
import {downloadBlob} from '../training/export.js';
import {approach} from './rules.js';

const style = `
.dive-sheet{font:14px/1.4 system-ui,sans-serif;color:#193943;background:#f7faf9;padding:20px}
dialog.dive-sheet{width:min(860px,88vw);max-height:82vh;overflow:auto;border:1px solid #91aeb3;border-radius:8px}
.dive-sheet::backdrop{background:#04151dcc}
.dive-sheet h2,.dive-sheet h3{color:#104553;margin:10px 0 6px}
.dive-sheet p{margin:4px 0}.dive-sheet header{border-bottom:2px solid #376978;padding-bottom:8px}
.dive-sheet nav{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}
.dive-sheet button{font:inherit;color:#12475b;background:white;border:1px solid #9ebbc0;padding:4px 10px;cursor:pointer}
.dive-plots{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}
.dive-plots figure{margin:0;border:1px solid #bacdd1;padding:8px;background:white}
.dive-plots svg{display:block;width:100%;height:70px}.dive-plots small{font-size:11px}
.dive-sheet ol{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px;list-style:none;padding:0}
.dive-sheet li{overflow-wrap:anywhere}.dive-sheet li button{margin-right:8px}
@media(max-width:640px){.dive-plots,.dive-sheet ol{grid-template-columns:1fr 1fr}}
@page{size:A4 portrait;margin:12mm}
@media print{.dive-sheet{padding:0;background:white}.dive-plots{grid-template-columns:repeat(3,1fr)}}
`;

function append(parent, tag, text) {
  const el = document.createElement(tag);
  if (text != null) el.textContent = text;
  parent.append(el);
  return el;
}

function csv(record) {
  const rows = [['time_s', 'event', 'detail', 'depth_m', 'heading_deg', 'speed_m_s', 'tension_N', 'paid_out_m',
    'north_m', 'east_m']];
  for (const r of record.samples) rows.push([r.t, '', '', ...channels.map(k => r[k]), ...(r.pos || []).slice(0, 2)]);
  for (const e of record.events) rows.push([e.t, e.kind, e.detail, '', '', '', '', '', '', '']);
  const header = rows.shift();
  rows.sort((a,b) => a[0] - b[0]);
  return [header, ...rows].map(row => row.map(value => {
    let text = String(value ?? '');
    if (typeof value === 'string' && /^[=+@\-\t\r]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  }).join(',')).join('\r\n');
}

export function openDiveReport(clip, seek) {
  if (!clip?.frames?.length) return;
  let record = clip.dive;
  if (!record) {
    const recorder = createDiveRecord(clip.world);
    for (const f of clip.frames) recorder.observe(f);
    record = recorder.snapshot();
  }
  const dialog = append(document.body, 'dialog');
  dialog.className = 'dive-sheet';
  append(dialog, 'style', style);
  const article = append(dialog, 'article');
  const header = append(article, 'header');
  append(header, 'small', S.local);
  append(header, 'h2', S.title);
  append(header, 'p', [clip.title, clip.frames[0].vehicle_id].filter(Boolean).join(' · '));
  if (clip.trainee) append(header, 'p', [clip.trainee.name, clip.trainee.lesson, clip.trainee.date]
    .filter(Boolean).join(' · '));
  const nav = append(article, 'nav');
  append(nav, 'button', S.close).onclick = () => dialog.close();
  append(nav, 'button', S.csv).onclick = () => downloadBlob('dive.csv', csv(record), 'text/csv;charset=utf-8');
  append(nav, 'button', S.html).onclick = printEdition;
  drawPlots(article, record, clip.world);
  append(article, 'h3', S.review);
  const comments = findings(record.metrics);
  if (!comments.length) append(article, 'p', S.noData);
  for (const rule of comments) {
    const value = record.metrics[rule.metric];
    append(article, 'p', S[rule.message].replace('{v}', String(+value.toFixed(2)))
      .replace('{limit}', String(approach.targetMps)));
  }
  const title = append(article, 'h3', S.timeline);
  const list = append(article, 'ol');
  const start = clip.frames[0].t;
  for (const e of record.events) {
    const item = append(list, 'li');
    const t = Math.max(0, e.t - start);
    append(item, 'button', t.toFixed(1) + ' s').onclick = () => {
      dialog.close();
      seek(t);
    };
    append(item, 'span', [S[e.kind] || e.kind, e.detail].filter(Boolean).join(' · '));
  }
  function printEdition() {
    const doc = document.implementation.createHTMLDocument(S.title);
    doc.documentElement.lang = document.documentElement.lang;
    const meta = append(doc.head, 'meta');
    meta.setAttribute('charset', 'utf-8');
    append(doc.head, 'style', style);
    doc.body.className = 'dive-sheet';
    for (const el of article.children) {
      if (el !== nav && el !== title && el !== list) doc.body.append(el.cloneNode(true));
    }
    append(doc.body, 'h3', S.summary);
    const counts = new Map();
    for (const e of record.events) counts.set(e.kind, (counts.get(e.kind) || 0) + 1);
    append(doc.body, 'p', [...counts].map(([k, n]) => (S[k] || k) + ' × ' + n).join(' · '));
    const evidence = append(doc.body, 'ol');
    for (const kind of ['peak', 'collision', 'snag', 'returned', 'released', 'measure', 'abort']) {
      const event = record.events.find(e => e.kind === kind);
      if (event) append(evidence, 'li', [(event.t - start).toFixed(1) + ' s', S[kind], event.detail]
        .filter(Boolean).join(' · '));
    }
    downloadBlob('dive-report.html', '<!doctype html>' + doc.documentElement.outerHTML, 'text/html;charset=utf-8');
  }
  dialog.addEventListener('close', () => dialog.remove(), {once: true});
  dialog.showModal();
}
