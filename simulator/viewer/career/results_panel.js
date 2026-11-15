// Career part of the results screen (play/results.js) for a YX work order: the pay slip (base × quality −
// itemised deductions = net), reputation with the client, the logbook hours of this dive (real and assisted
// apart) and in total, the licence progress bar with the next exam, the exam verdict, newly opened work orders
// and equipment, and the deliverable record with its readings. DOM only; the numbers come from settle.js.

const STRINGS = {
  pay: '報酬',
  base: '基本報酬',
  repeat: '（重接 {rate}%）',
  quality: '品質加成 ×{x}',
  partialShare: '部分交件 ×{x}',
  net: '實領',
  moneyUnit: '元',
  balance: '帳戶餘額 {money} 元',
  reputation: '{client}聲譽 {delta}（累計 {total}）',
  hours: '本次駕駛 真實 {real} · 輔助 {assisted}',
  hoursTotal: '日誌累計 真實 {real} h · 輔助 {assisted} h',
  licence: '執照',
  licenceTop: '已是目前最高可取得的執照',
  nextLicence: '下一張：{label}',
  hoursNeed: '真實時數 {have} / {need} h',
  examNext: '考核：{title}',
  granted: '取得：{label}',
  unlocks: '新開放',
  unlockContract: '工單：{title}',
  unlockItem: '裝備部：{label}',
  deliverables: '交付紀錄',
  minutes: '{m} 分',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function money(value) {
  return Math.round(Number(value) || 0).toLocaleString('en-US');
}

function signed(value) {
  return value > 0 ? `+${value}` : String(value);
}

function minutes(seconds) {
  return STRINGS.minutes.replace('{m}', String(Math.round((Number(seconds) || 0) / 60)));
}

function line(label, value, className = '') {
  const row = element('div', `career-slip-row ${className}`.trim());
  row.append(element('span', '', label), element('b', '', value));
  return row;
}

function paySlip(summary) {
  const pay = summary.pay;
  const box = element('section', 'career-slip');
  box.dataset.outcome = pay.outcome;
  box.append(element('h3', 'menu-label', STRINGS.pay));
  const base = pay.repeat ? `${STRINGS.base}${STRINGS.repeat.replace('{rate}', String(Math.round(pay.rate * 100)))}`
    : STRINGS.base;
  box.append(line(base, money(pay.base)));
  if (pay.outcome === 'complete') {
    box.append(line(STRINGS.quality.replace('{x}', pay.quality.toFixed(2)), money(pay.gross)));
  } else if (pay.outcome === 'partial') {
    box.append(line(STRINGS.partialShare.replace('{x}', pay.quality.toFixed(2)), money(pay.gross)));
  }
  for (const entry of pay.penalties) box.append(line(entry.label, `−${money(entry.amount)}`, 'career-slip-minus'));
  if (pay.deduction > 0 && !pay.penalties.length) box.append(line('', `−${money(pay.deduction)}`));
  const net = line(STRINGS.net, `${money(pay.net)} ${STRINGS.moneyUnit}`, 'career-slip-net');
  net.id = 'resultsPay';
  box.append(net);
  box.append(element('p', 'menu-help', STRINGS.balance.replace('{money}', money(summary.money))));
  return box;
}

function standing(summary) {
  const box = element('section', 'career-standing');
  const rep = summary.reputation;
  box.append(element('p', 'career-rep', STRINGS.reputation.replace('{client}', rep.label)
    .replace('{delta}', signed(rep.delta)).replace('{total}', String(rep.total))));
  const hours = summary.hours;
  box.append(element('p', '', STRINGS.hours.replace('{real}', minutes(hours.real_s))
    .replace('{assisted}', minutes(hours.assisted_s))));
  box.append(element('p', 'menu-help', STRINGS.hoursTotal.replace('{real}', (hours.total_real_s / 3600).toFixed(1))
    .replace('{assisted}', (hours.total_assisted_s / 3600).toFixed(1))));
  return box;
}

function licenceBox(summary) {
  const box = element('section', 'career-licence');
  box.id = 'resultsLicence';
  const progress = summary.licence.progress;
  box.append(element('h3', 'menu-label', STRINGS.licence));
  box.append(element('strong', 'career-licence-name', progress.current.label));
  if (summary.exam.passed) {
    box.append(element('p', 'career-granted', STRINGS.granted.replace('{label}', summary.exam.granted)));
  }
  if (!progress.next) {
    box.append(element('p', 'menu-help', STRINGS.licenceTop));
    return box;
  }
  const bar = element('div', 'career-bar');
  bar.setAttribute('role', 'progressbar');
  bar.setAttribute('aria-valuemin', '0');
  bar.setAttribute('aria-valuemax', '100');
  bar.setAttribute('aria-valuenow', String(Math.round(progress.fraction * 100)));
  const fill = element('i');
  fill.style.width = `${Math.round(progress.fraction * 100)}%`;
  bar.append(fill);
  box.append(element('p', '', STRINGS.nextLicence.replace('{label}', progress.next.label)), bar);
  const notes = [];
  if (progress.requiredHours > 0) {
    notes.push(STRINGS.hoursNeed.replace('{have}', progress.realHours.toFixed(2))
      .replace('{need}', String(progress.requiredHours)));
  }
  if (progress.exam) notes.push(STRINGS.examNext.replace('{title}', progress.exam.title));
  box.append(element('p', 'menu-help', notes.join(' · ')));
  return box;
}

function unlocksBox(summary) {
  const items = [
    ...summary.unlocks.contracts.map(function contract(entry) {
      return STRINGS.unlockContract.replace('{title}', entry.title);
    }),
    ...summary.unlocks.items.map(function item(entry) {
      return STRINGS.unlockItem.replace('{label}', entry.label);
    }),
  ];
  if (!items.length) return null;
  const box = element('section', 'career-unlocks');
  box.id = 'resultsUnlocks';
  box.append(element('h3', 'menu-label', STRINGS.unlocks));
  const list = element('ul');
  list.append(...items.map(function row(text) {
    return element('li', '', text);
  }));
  box.append(list);
  return box;
}

/** The deliverable record for the rewards column: [text] with ✓/✗ and readings. */
export function deliverableLines(summary) {
  return (summary.line?.deliverables || []).map(function text(entry) {
    const mark = entry.done ? '✓' : '✗';
    return `${mark} ${entry.label}${entry.reading ? `：${entry.reading}` : ''}`;
  });
}

export const DELIVERABLES_TITLE = STRINGS.deliverables;

/** Fills container with the career panel of an outcome; hides it when the outcome is not a work order. */
export function renderCareerPanel(container, outcome) {
  const summary = outcome?.career;
  container.replaceChildren();
  container.hidden = !summary;
  if (!summary) return;
  const unlocks = unlocksBox(summary);
  container.append(paySlip(summary), standing(summary), licenceBox(summary));
  if (unlocks) container.append(unlocks);
}
