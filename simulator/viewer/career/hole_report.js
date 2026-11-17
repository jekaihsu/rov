// Clock-bearing and depth report sheet for aquaculture net holes (C2-1 / C2-3).
// Pure presentation: the player picks a clock hour and a depth, then the career tracker compares them
// to the hole truth from the contract. Mounted beside the objective card while a reportable item waits.
import { localize } from '../i18n/index.js';

const STRINGS = localize('career.hole_report', {
  title: '破洞回報',
  clock: '時鐘方位',
  depth: '深度（公尺）',
  submit: '送出回報',
  hint: '以箱網中心為 12 點鐘（北），報整點方位與大約深度。',
  clockUnit: '點鐘',
  depthUnit: 'm',
});

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

let styleReady = false;

function ensureStyle() {
  if (styleReady || typeof document === 'undefined') return;
  styleReady = true;
  const style = document.createElement('style');
  style.textContent = `
    .hole-report{margin-top:10px;padding:10px 12px;border-left:2px solid #4fd1e0;background:rgba(8,18,26,.55)}
    .hole-report h4{margin:0 0 6px;font-size:13px;letter-spacing:.08em;color:#4fd1e0;font-weight:600}
    .hole-report p{margin:0 0 8px;font-size:12px;color:#8fa6b2;line-height:1.4}
    .hole-report .hr-row{display:flex;gap:8px;align-items:center;margin:6px 0;flex-wrap:wrap}
    .hole-report label{font-size:12px;color:#cfe0e8;min-width:4.5em}
    .hole-report select,.hole-report input{background:#0b1a22;color:#e8f1f5;border:1px solid #2a4552;
      padding:4px 8px;font:inherit;min-width:4.5em}
    .hole-report button{pointer-events:auto;margin-top:8px;padding:6px 12px;background:#f05a28;color:#fff;
      border:0;font:inherit;cursor:pointer}
    .hole-report button:focus-visible{outline:2px solid #4fd1e0}
    .hole-report[hidden]{display:none}
  `;
  document.head.append(style);
}

/**
 * onSubmit(id, {clock, depth}): called when the player sends a report.
 * Returns a DOM node with {show(item), hide(), root}.
 */
export function createHoleReport({ onSubmit } = {}) {
  ensureStyle();
  const root = element('div', 'hole-report');
  root.hidden = true;
  const title = element('h4', '', STRINGS.title);
  const hint = element('p', '', STRINGS.hint);
  const clockRow = element('div', 'hr-row');
  const clockLabel = element('label', '', STRINGS.clock);
  clockLabel.htmlFor = 'holeReportClock';
  const clock = document.createElement('select');
  clock.id = 'holeReportClock';
  for (let hour = 1; hour <= 12; hour += 1) {
    const option = document.createElement('option');
    option.value = String(hour);
    option.textContent = `${hour} ${STRINGS.clockUnit}`;
    clock.append(option);
  }
  clock.value = '6';
  clockRow.append(clockLabel, clock);
  const depthRow = element('div', 'hr-row');
  const depthLabel = element('label', '', STRINGS.depth);
  depthLabel.htmlFor = 'holeReportDepth';
  const depth = document.createElement('input');
  depth.id = 'holeReportDepth';
  depth.type = 'number';
  depth.min = '0';
  depth.max = '30';
  depth.step = '0.5';
  depth.value = '7';
  const depthUnit = element('span', '', STRINGS.depthUnit);
  depthRow.append(depthLabel, depth, depthUnit);
  const submit = element('button', '', STRINGS.submit);
  submit.type = 'button';
  let activeId = null;
  submit.addEventListener('click', function send() {
    if (!activeId || !onSubmit) return;
    onSubmit(activeId, { clock: Number(clock.value), depth: Number(depth.value) });
  });
  root.append(title, hint, clockRow, depthRow, submit);

  function show(item) {
    activeId = item?.id || null;
    root.hidden = !activeId;
    if (item?.truth?.clock) clock.value = String(Math.round(Number(item.truth.clock)) || 6);
    if (item?.truth?.depth != null) depth.value = String(Number(item.truth.depth));
  }
  function hide() {
    activeId = null;
    root.hidden = true;
  }
  return { root, show, hide };
}
