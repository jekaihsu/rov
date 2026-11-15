// Contract detail screen of the YX board. Big-picture layout: the 3D stage shows the site; the hero block holds
// only what is needed to decide (client and job type, title, seabed depth, current, pay, up to three requirement
// chips with ✓/✗ against the career save, the vehicles it allows) and the one primary button that launches the
// dive. The full work order (brief, conditions, deliverables, every requirement, medal targets, the exam rules)
// opens behind 明細. An exam says before launch that it forces the `real` fidelity preset and restores the
// player's settings afterwards; accepting it takes a second, explicit confirmation.
import { siteFacts } from '../menu/catalogue.js';
import {
  chip,
  createDetailSheet,
  createHero,
  detailButton,
  element,
  linkButton,
  primaryButton,
  statusLine,
} from '../menu/big_picture.js';
import { MEDALS, medalLabel } from '../play/results_model.js';
import { vehicleName } from '../fleet_names.js';
import { moneyText } from './board.js';
import { clientLabel, contractStatus, gradeFor, hasLicence, itemLabel, jobLabel } from './rules.js';
import { DELIVERABLE_KIND_LABELS } from './scoring.js';

const STRINGS = {
  kicker: '{client} · {job}',
  client: '業主',
  pay: '報酬',
  depth: '海床',
  current: '洋流',
  moneyUnit: '元',
  site: '現場',
  siteLine: '海床 {depth} m · 能見度 {visibility} m · 最大洋流 {current} kn · 纜長 {tether} m',
  brief: '工單',
  deliverables: '交付項目',
  optional: '（加分）',
  requirements: '接案條件',
  licence: '{label}',
  licenceFull: '執照：{label}',
  equipment: '{label}',
  equipmentFull: '裝備：{label}',
  vehicles: '可派載具',
  medalsTitle: '獎章目標',
  medalItem: '{medal} {min} 分',
  repeat: '已完成過：再接可領 {rate}% 報酬。',
  examTitle: 'YX 執照考核',
  examChip: '執照考核 · 強制真實模式',
  examText: '考核全程強制使用「真實」擬真設定（無飛行輔助、無第三人稱、有影像延遲），結束後自動恢復你原本的設定。'
    + '只有真實模式的駕駛時數計入執照；考核中若改開輔助，本次不計。',
  examGrants: '通過後取得：{label}',
  accept: '接案下水',
  acceptExam: '接受考核',
  confirmExam: '確認：真實模式下水',
  locked: '尚未開放',
  back: '返回看板',
  provisional: '場景籌備中，座標為暫定。',
  summary: '{licence} · {money} 元',
};
const MAX_CHIPS = 3;

function fixed(value, digits = 0) {
  return Number.isFinite(value) ? value.toFixed(digits) : '—';
}

function check(ok, text) {
  const item = element('li', 'career-check', text);
  item.dataset.ok = String(!!ok);
  return item;
}

function paragraph(text) {
  return element('p', 'bp-sheet-text', text);
}

/** ctx.career: career/menu.js context. ctx.launchContract(contract, model) starts the dive. */
export function buildContractScreen(ctx) {
  const career = ctx.career;
  const root = element('section', 'menu-screen bp-screen');
  root.dataset.screen = 'contract';
  const summary = statusLine('contractSummary');
  const hero = createHero();
  hero.element.classList.add('career-detail');
  hero.title.id = 'contractTitle';
  // Shown for an exam only: the short form of the rule; the full text is in the details sheet.
  const exam = chip(STRINGS.examChip, 'warn');
  exam.id = 'contractExam';
  const vehicles = element('div', 'menu-vehicles');
  vehicles.setAttribute('role', 'radiogroup');
  vehicles.setAttribute('aria-label', STRINGS.vehicles);
  const { button: accept, label: acceptText } = primaryButton('contractAccept', STRINGS.accept);
  accept.dataset.autofocus = '';
  const sheet = createDetailSheet(STRINGS.brief);
  const back = linkButton('contractBack', STRINGS.back);
  back.addEventListener('click', function goBack() {
    ctx.back();
  });
  hero.chips.after(vehicles);
  hero.actions.append(accept, detailButton('contractDetails', sheet), back);
  root.append(summary, hero.element);
  let contract = null;
  let model = 'x1';
  let confirming = false;

  function renderVehicles() {
    vehicles.replaceChildren(...contract.vehicles.map(function vehicleChip(id) {
      const button = element('button', 'menu-chip', vehicleName(id));
      button.type = 'button';
      button.dataset.vehicle = id;
      button.setAttribute('aria-pressed', String(id === model));
      button.addEventListener('click', function chooseVehicle() {
        model = id;
        ctx.selectModel(id);
        renderVehicles();
        vehicles.querySelector(`[data-vehicle="${id}"]`)?.focus({ preventScroll: true });
      });
      return button;
    }));
  }
  // Every requirement as {ok, short, full}: the licence, each piece of equipment, then the other lock reasons.
  function requirements(status) {
    const { data, save } = career;
    const grade = gradeFor(data, contract.licence).label;
    const list = [{
      ok: hasLicence(save, data, contract.licence),
      short: STRINGS.licence.replace('{label}', grade),
      full: STRINGS.licenceFull.replace('{label}', grade),
    }];
    for (const id of contract.equipment || []) {
      const label = itemLabel(data, id);
      list.push({
        ok: save.owned.includes(id),
        short: STRINGS.equipment.replace('{label}', label),
        full: STRINGS.equipmentFull.replace('{label}', label),
      });
    }
    for (const reason of status.reasons) {
      if (reason.kind === 'licence' || reason.kind === 'equipment') continue;
      list.push({ ok: false, short: reason.text, full: reason.text });
    }
    return list;
  }
  function renderChips(needs) {
    // What is missing comes first, so the three chips always show why a work order is closed.
    const ordered = [...needs].sort(function missingFirst(a, b) {
      return Number(a.ok) - Number(b.ok);
    });
    const chips = ordered.slice(0, contract.exam ? MAX_CHIPS - 1 : MAX_CHIPS).map(function needChip(entry) {
      return chip(`${entry.ok ? '✓' : '✗'} ${entry.short}`, entry.ok ? 'ok' : 'missing');
    });
    if (contract.exam) chips.unshift(exam);
    hero.chips.replaceChildren(...chips);
  }
  function goalItems() {
    const list = contract.deliverables.map(function goal(entry) {
      const kind = DELIVERABLE_KIND_LABELS[entry.kind] || '';
      const label = `${kind ? `${kind} · ` : ''}${entry.label}${entry.required === false ? STRINGS.optional : ''}`;
      return element('li', '', label);
    });
    if (!list.length && contract.radio?.start) list.push(element('li', '', contract.radio.start));
    return list;
  }
  function renderStats(facts) {
    const stats = [];
    if (facts) {
      stats.push([STRINGS.depth, fixed(facts.deep), 'm']);
      stats.push([STRINGS.current, fixed(contract.currentKn ?? facts.current, 1), 'kn']);
    }
    stats.push([STRINGS.pay, moneyText(contract.pay), STRINGS.moneyUnit]);
    hero.setStats(stats);
  }
  function renderSheet(status, needs, facts) {
    const { data } = career;
    sheet.setTitle(contract.title);
    sheet.clear();
    const notes = [contract.conditions || ''];
    if (status.repeat) notes.push(STRINGS.repeat.replace('{rate}', String(Math.round(career.repeatRate * 100))));
    if (contract.provisional) notes.push(STRINGS.provisional);
    const client = `${clientLabel(data, contract.client)}｜${contract.clientName}`;
    sheet.section(STRINGS.client, paragraph(client));
    sheet.section(STRINGS.brief, paragraph(contract.brief), paragraph(notes.filter(Boolean).join(' ')));
    if (facts) {
      sheet.section(STRINGS.site, paragraph(STRINGS.siteLine.replace('{depth}', fixed(facts.deep))
        .replace('{visibility}', fixed(facts.visibility))
        .replace('{current}', fixed(contract.currentKn ?? facts.current, 1))
        .replace('{tether}', fixed(facts.tether))));
    }
    const goals = element('ol', 'menu-objectives');
    goals.append(...goalItems());
    sheet.section(STRINGS.deliverables, goals);
    const checks = element('ul', 'career-checks');
    checks.append(...needs.map(function row(entry) {
      return check(entry.ok, entry.full);
    }));
    sheet.section(STRINGS.requirements, checks);
    sheet.section(STRINGS.medalsTitle, paragraph(MEDALS.map(function medalText(medal) {
      return STRINGS.medalItem.replace('{medal}', medalLabel(medal.id)).replace('{min}', String(medal.min));
    }).join(' · ')));
    if (!contract.exam) return;
    const grants = contract.exam.grants ? gradeFor(data, contract.exam.grants).label : '';
    const endorsement = data.endorsements.find(function byId(entry) {
      return entry.id === contract.exam.endorsement;
    })?.label || '';
    sheet.section(STRINGS.examTitle, paragraph(STRINGS.examText),
      paragraph(STRINGS.examGrants.replace('{label}', grants || endorsement)));
  }
  function render() {
    if (!contract) return;
    const { data, save } = career;
    const status = contractStatus(contract, save, data, career.sceneKeys);
    root.dataset.status = status.status;
    root.dataset.contract = contract.id;
    summary.textContent = STRINGS.summary.replace('{licence}', gradeFor(data, save.licence).label)
      .replace('{money}', moneyText(save.money));
    hero.kicker.textContent = STRINGS.kicker.replace('{client}', clientLabel(data, contract.client))
      .replace('{job}', jobLabel(data, contract.job));
    hero.setTitle(contract.title);
    const scene = career.sceneFor(contract.scenario);
    const facts = scene ? siteFacts(scene) : null;
    const needs = requirements(status);
    renderStats(facts);
    renderChips(needs);
    renderSheet(status, needs, facts);
    if (!contract.vehicles.includes(model)) model = contract.vehicles[0];
    renderVehicles();
    accept.disabled = !status.available;
    let label = contract.exam ? STRINGS.acceptExam : STRINGS.accept;
    if (confirming) label = STRINGS.confirmExam;
    if (!status.available) label = STRINGS.locked;
    acceptText.textContent = label;
    accept.dataset.confirming = String(confirming);
  }
  accept.addEventListener('click', function acceptContract() {
    if (!contract || accept.disabled) return;
    if (contract.exam && !confirming) {
      confirming = true;
      render();
      return;
    }
    ctx.launchContract(contract, model);
  });
  return {
    element: root,
    pose: 'briefing',
    // The site the 3D stage shows behind the work order.
    sceneKey() {
      return contract?.scenario || '';
    },
    show(next) {
      contract = next;
      confirming = false;
      model = ctx.choice.model;
    },
    enter() {
      confirming = false;
      render();
    },
  };
}
