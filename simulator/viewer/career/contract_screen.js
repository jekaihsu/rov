// Contract detail screen of the YX board: the full work order (client, site, job type, brief, conditions, pay,
// medal targets, deliverables), what it requires with ✓/✗ against the career save, the vehicles it allows, and
// the accept button that launches the dive. An exam says before launch that it forces the `real` fidelity preset
// and restores the player's settings afterwards; accepting it takes a second, explicit confirmation.
import { readout } from '../menu/screens.js';
import { siteFacts } from '../menu/catalogue.js';
import { MEDALS, medalLabel } from '../play/results_model.js';
import { vehicleName } from '../fleet_names.js';
import { moneyText } from './board.js';
import { clientLabel, contractStatus, gradeFor, hasLicence, itemLabel, jobLabel } from './rules.js';
import { DELIVERABLE_KIND_LABELS } from './scoring.js';

const STRINGS = {
  kicker: '{client} · {job}',
  pay: '報酬',
  depth: '海床深度',
  visibility: '能見度',
  current: '最大洋流',
  tether: '纜長',
  moneyUnit: '元',
  deliverables: '交付項目',
  optional: '（加分）',
  requirements: '接案條件',
  licence: '執照：{label}',
  equipment: '裝備：{label}',
  vehicles: '可派載具',
  medals: '獎章目標：{list}',
  medalItem: '{medal} {min} 分',
  repeat: '已完成過：再接可領 {rate}% 報酬。',
  examTitle: 'YX 執照考核',
  examText: '考核全程強制使用「真實」擬真設定（無飛行輔助、無第三人稱、有影像延遲），結束後自動恢復你原本的設定。'
    + '只有真實模式的駕駛時數計入執照；考核中若改開輔助，本次不計。',
  examGrants: '通過後取得：{label}',
  accept: '接案下水',
  acceptExam: '接受考核',
  confirmExam: '確認：以真實模式下水',
  locked: '尚未開放',
  back: '返回看板',
  provisional: '場景籌備中，座標為暫定。',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function fixed(value, digits = 0) {
  return Number.isFinite(value) ? value.toFixed(digits) : '—';
}

function check(ok, text) {
  const item = element('li', 'career-check', text);
  item.dataset.ok = String(!!ok);
  return item;
}

/** ctx.career: career/menu.js context. ctx.launchContract(contract, model) starts the dive. */
export function buildContractScreen(ctx) {
  const career = ctx.career;
  const root = element('section', 'menu-screen');
  root.dataset.screen = 'contract';
  const panel = element('div', 'menu-briefing career-detail');
  const main = element('div', 'career-detail-main');
  const kicker = element('p', 'menu-kicker');
  const heading = element('h2', 'menu-heading menu-heading-large');
  heading.id = 'contractTitle';
  const brief = element('p', 'menu-brief');
  const numbers = element('div', 'menu-readouts');
  const conditions = element('p', 'menu-help');
  const columns = element('div', 'career-detail-columns');
  const goalsBox = element('div');
  const goals = element('ol', 'menu-objectives');
  goalsBox.append(element('h3', 'menu-label', STRINGS.deliverables), goals);
  const needsBox = element('div');
  const needs = element('ul', 'career-checks');
  needsBox.append(element('h3', 'menu-label', STRINGS.requirements), needs);
  columns.append(goalsBox, needsBox);
  const medals = element('p', 'menu-help career-medals');
  main.append(kicker, heading, brief, numbers, conditions, columns, medals);
  const side = element('div', 'menu-launch-actions career-actions');
  const exam = element('div', 'career-exam');
  exam.id = 'contractExam';
  const examGrant = element('p', 'career-exam-grant');
  exam.append(element('strong', '', STRINGS.examTitle), element('p', '', STRINGS.examText), examGrant);
  const vehiclesTitle = element('h3', 'menu-label', STRINGS.vehicles);
  const vehicles = element('div', 'menu-vehicles');
  vehicles.setAttribute('role', 'radiogroup');
  const note = element('p', 'menu-help');
  note.id = 'contractNote';
  const accept = element('button', 'menu-start');
  accept.type = 'button';
  accept.id = 'contractAccept';
  accept.dataset.autofocus = '';
  const acceptText = element('span', '', STRINGS.accept);
  const cap = element('span', 'menu-press-cap');
  cap.dataset.promptAction = 'accept';
  accept.append(cap, acceptText);
  const back = element('button', 'menu-next', STRINGS.back);
  back.type = 'button';
  back.id = 'contractBack';
  back.addEventListener('click', function goBack() {
    ctx.back();
  });
  side.append(exam, vehiclesTitle, vehicles, note, accept, back);
  panel.append(main, side);
  root.append(panel);
  let contract = null;
  let model = 'x1';
  let confirming = false;

  function renderVehicles() {
    vehicles.replaceChildren(...contract.vehicles.map(function chip(id) {
      const button = element('button', 'menu-chip', vehicleName(id));
      button.type = 'button';
      button.dataset.vehicle = id;
      button.setAttribute('aria-pressed', String(id === model));
      button.addEventListener('click', function chooseVehicle() {
        model = id;
        ctx.selectModel(id);
        renderVehicles();
      });
      return button;
    }));
  }
  function renderNeeds(status) {
    const { data, save } = career;
    const items = [check(hasLicence(save, data, contract.licence),
      STRINGS.licence.replace('{label}', gradeFor(data, contract.licence).label))];
    for (const id of contract.equipment || []) {
      items.push(check(save.owned.includes(id), STRINGS.equipment.replace('{label}', itemLabel(data, id))));
    }
    for (const reason of status.reasons) {
      if (reason.kind === 'licence' || reason.kind === 'equipment') continue;
      items.push(check(false, reason.text));
    }
    needs.replaceChildren(...items);
  }
  function renderGoals() {
    const list = contract.deliverables.map(function goal(entry) {
      const kind = DELIVERABLE_KIND_LABELS[entry.kind] || '';
      const label = `${kind ? `${kind} · ` : ''}${entry.label}${entry.required === false ? STRINGS.optional : ''}`;
      return element('li', '', label);
    });
    if (!list.length && contract.radio?.start) list.push(element('li', '', contract.radio.start));
    goals.replaceChildren(...list);
  }
  function renderNumbers() {
    numbers.replaceChildren(readout(STRINGS.pay, moneyText(contract.pay), STRINGS.moneyUnit));
    const scene = career.sceneFor(contract.scenario);
    if (!scene) return;
    const facts = siteFacts(scene);
    numbers.append(
      readout(STRINGS.depth, fixed(facts.deep), 'm'),
      readout(STRINGS.visibility, fixed(facts.visibility), 'm'),
      readout(STRINGS.current, fixed(facts.current, 1), 'kn'),
      readout(STRINGS.tether, fixed(facts.tether), 'm'),
    );
  }
  function render() {
    if (!contract) return;
    const { data, save } = career;
    const status = contractStatus(contract, save, data, career.sceneKeys);
    root.dataset.status = status.status;
    root.dataset.contract = contract.id;
    const client = `${clientLabel(data, contract.client)}｜${contract.clientName}`;
    kicker.textContent = STRINGS.kicker.replace('{client}', client).replace('{job}', jobLabel(data, contract.job));
    heading.textContent = contract.title;
    brief.textContent = contract.brief;
    renderNumbers();
    const notes = [contract.conditions || ''];
    if (status.repeat) notes.push(STRINGS.repeat.replace('{rate}', String(Math.round(career.repeatRate * 100))));
    if (contract.provisional) notes.push(STRINGS.provisional);
    conditions.textContent = notes.filter(Boolean).join(' ');
    renderGoals();
    renderNeeds(status);
    medals.textContent = STRINGS.medals.replace('{list}', MEDALS.map(function medalText(medal) {
      return STRINGS.medalItem.replace('{medal}', medalLabel(medal.id)).replace('{min}', String(medal.min));
    }).join(' · '));
    exam.hidden = !contract.exam;
    const grants = contract.exam?.grants ? gradeFor(data, contract.exam.grants).label : '';
    const endorsement = data.endorsements.find(function byId(entry) {
      return entry.id === contract.exam?.endorsement;
    })?.label || '';
    examGrant.textContent = STRINGS.examGrants.replace('{label}', grants || endorsement);
    if (!contract.vehicles.includes(model)) model = contract.vehicles[0];
    renderVehicles();
    accept.disabled = !status.available;
    note.textContent = status.available ? '' : status.reasons.map(function reason(entry) {
      return entry.text;
    }).join('；');
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
    show(next) {
      contract = next;
      confirming = false;
      model = ctx.choice.model;
    },
    enter() {
      confirming = false;
      render();
      if (contract) ctx.previewScene(contract.scenario);
    },
  };
}
