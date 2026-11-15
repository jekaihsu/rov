/* Build a single-page HTML debrief report for download / print-to-PDF. */
import {STRINGS} from './strings.js';

function esc(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

export function buildDebriefHtml({
  report = {},
  events = [],
  notes = '',
  screenshots = [],
  strings = STRINGS,
} = {}) {
  const s = strings;
  const completion = report.completion || {};
  const score = completion.score ?? report.score ?? s.missing;
  const elapsed = report.elapsed ?? completion.elapsed ?? s.missing;
  const vehicle = report.vehicle_id ?? s.missing;
  const noteText = notes || report.debrief?.notes || s.notesPlaceholder;
  const rows = events.map(function row(event) {
    const label = s[event.kind] || event.kind;
    return `<tr><td>${esc(event.t)} ${esc(s.seconds)}</td><td>${esc(label)}</td><td>${esc(event.detail || '')}</td></tr>`;
  }).join('') || `<tr><td colspan="3">${esc(s.missing)}</td></tr>`;
  const shots = (screenshots.length ? screenshots : [{caption: s.noScreenshot}]).map(function figure(shot) {
    const caption = esc(shot.caption ?? shot.t ?? '');
    if (shot.src) {
      return `<figure><img src="${esc(shot.src)}" alt="${caption}"><figcaption>${caption}</figcaption></figure>`;
    }
    return `<figure><figcaption>${caption}</figcaption></figure>`;
  }).join('');
  return `<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>${esc(s.title)}</title>
<style>
body{font:15px/1.45 system-ui,sans-serif;color:#102018;background:#f4f7f5;margin:24px}
h1{font-size:28px;margin:0 0 4px}
.eyebrow{letter-spacing:.12em;text-transform:uppercase;color:#4a6a58;font-size:12px}
.meta{display:flex;gap:18px;flex-wrap:wrap;margin:16px 0}
.meta div{background:#fff;border:1px solid #c5d5cb;padding:10px 14px;min-width:120px}
.meta strong{display:block;font-size:22px}
table{border-collapse:collapse;width:100%;background:#fff}
th,td{border:1px solid #c5d5cb;padding:8px;text-align:left}
th{background:#e4eee7}
.notes{white-space:pre-wrap;background:#fff;border:1px solid #c5d5cb;padding:12px;min-height:4em}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
figure{margin:0;background:#fff;border:1px solid #c5d5cb;padding:8px}
img{max-width:100%;height:auto;display:block}
.banner{background:#1c3a2c;color:#e8f5ec;padding:8px 12px;margin:12px 0}
@media print{body{background:#fff;margin:12px}}
</style>
</head>
<body>
<p class="eyebrow">${esc(s.subtitle)}</p>
<h1>${esc(s.title)}報告</h1>
<p>${esc(s.provisional)}</p>
<div class="banner">${esc(s.viewpointBanner)}</div>
<section class="meta">
  <div><span>${esc(s.vehicle)}</span><strong>${esc(vehicle)}</strong></div>
  <div><span>${esc(s.score)}</span><strong>${esc(score)}</strong></div>
  <div><span>${esc(s.elapsed)}</span><strong>${esc(elapsed)} ${esc(s.seconds)}</strong></div>
</section>
<h2>${esc(s.events)}</h2>
<table>
<thead><tr><th>t</th><th>kind</th><th>detail</th></tr></thead>
<tbody>${rows}</tbody>
</table>
<h2>${esc(s.notes)}</h2>
<div class="notes">${esc(noteText)}</div>
<h2>${esc(s.screenshots)}</h2>
<div class="grid">${shots}</div>
</body>
</html>`;
}

export function downloadDebriefHtml(filename, html) {
  const url = URL.createObjectURL(new Blob([html], {type: 'text/html;charset=utf-8'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename || 'debrief-report.html';
  link.click();
  setTimeout(function revoke() { URL.revokeObjectURL(url); }, 1000);
}
