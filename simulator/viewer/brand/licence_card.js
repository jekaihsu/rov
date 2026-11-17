// YX pilot licence certificate: an archival-looking card in the identity's paper and ink system.
// licenceCard(props) returns an element; it is not wired to any save. The career system passes the holder's
// grade, name, issue date, logged hours and serial. licenceModel(props) is the DOM-free part (texts and index
// numbers) so node tests and other views can share the same formatting.
// YX is the fictional issuer of the game (docs/design/game-plan.md §9); no real organisation is named.
import {svgNode, yxMark} from './marks.js';
import { localize } from '../i18n/index.js';

export const STRINGS = localize('brand.licence_card', {
  heading: 'ROV 操作員執照',
  headingCaption: 'REMOTELY OPERATED VEHICLE · PILOT LICENCE',
  issuer: 'YX 發照',
  issuerCaption: 'ISSUED BY YX',
  cardLabel: 'YX 操作員執照',
  gradeCaption: 'GRADE',
  fields: {
    holder: '持照人',
    serial: '證號',
    issued: '發照日期',
    hoursReal: '真實模式時數',
    hoursAssisted: '輔助模式時數',
  },
  hoursUnit: 'h',
  empty: '—',
  stub: 'YX · PILOT LICENCE · RETAIN THIS STUB',
  grades: {
    trainee: {title: '見習駕駛員', short: '見習', caption: 'TRAINEE PILOT'},
    grade2: {title: '二級駕駛員', short: '二級', caption: 'PILOT · CLASS II'},
    grade1: {title: '一級駕駛員', short: '一級', caption: 'PILOT · CLASS I'},
    senior: {title: '資深駕駛員', short: '資深', caption: 'SENIOR PILOT'},
    supervisor: {title: '主管', short: '主管', caption: 'SUPERVISOR'},
  },
});

/** Grade ids from lowest to highest. */
export const LICENCE_GRADES = Object.freeze(Object.keys(STRINGS.grades));

function pad2(value) {
  return String(value).padStart(2, '0');
}

function dateText(value) {
  if (value === null || value === undefined || value === '') return STRINGS.empty;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return `${date.getUTCFullYear()}.${pad2(date.getUTCMonth() + 1)}.${pad2(date.getUTCDate())}`;
}

function hoursText(value) {
  const hours = Number(value);
  if (value === null || value === undefined || value === '' || !Number.isFinite(hours) || hours < 0) {
    return STRINGS.empty;
  }
  return hours.toFixed(1);
}

/**
 * Texts of a licence. Unknown grades fall back to the lowest one; missing fields show a dash.
 * Returns {grade, index, count, title, short, caption, holder, serial, issued, hoursReal, hoursAssisted}.
 */
export function licenceModel({grade, holderName, issuedOn, hoursReal, hoursAssisted, serial} = {}) {
  const id = LICENCE_GRADES.includes(grade) ? grade : LICENCE_GRADES[0];
  const text = STRINGS.grades[id];
  return {
    grade: id,
    index: pad2(LICENCE_GRADES.indexOf(id) + 1),
    count: pad2(LICENCE_GRADES.length),
    title: text.title,
    short: text.short,
    caption: text.caption,
    holder: String(holderName || '').trim() || STRINGS.empty,
    serial: String(serial || '').trim() || STRINGS.empty,
    issued: dateText(issuedOn),
    hoursReal: hoursText(hoursReal),
    hoursAssisted: hoursText(hoursAssisted),
  };
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function field(label, value, unit) {
  const cell = element('div', 'brand-licence-field');
  cell.append(element('span', 'brand-caption', label));
  const line = element('b', '', value);
  if (unit && value !== STRINGS.empty) line.append(element('small', '', unit));
  cell.append(line);
  return cell;
}

function ladder(model) {
  const list = element('ol', 'brand-licence-ladder');
  for (const id of LICENCE_GRADES) {
    const step = element('li', 'brand-caption', STRINGS.grades[id].short);
    if (id === model.grade) step.setAttribute('aria-current', 'true');
    list.append(step);
  }
  return list;
}

function registration(corner) {
  const mark = element('i', `brand-registration brand-registration-${corner}`);
  mark.setAttribute('aria-hidden', 'true');
  return mark;
}

/**
 * The certificate element.
 * props: {grade: 'trainee'|'grade2'|'grade1'|'senior'|'supervisor', holderName, issuedOn (Date, ISO string or
 * ms), hoursReal, hoursAssisted, serial}.
 */
export function licenceCard(props = {}) {
  const model = licenceModel(props);
  const card = element('article', 'brand-licence brand-paper');
  card.dataset.grade = model.grade;
  card.setAttribute('aria-label', `${STRINGS.cardLabel}：${model.title}`);

  const stub = element('div', 'brand-licence-stub');
  stub.append(element('span', 'brand-licence-stub-index', model.index));
  stub.append(element('span', 'brand-caption brand-licence-stub-text', STRINGS.stub));
  stub.append(element('span', 'brand-caption brand-licence-stub-serial', model.serial));

  const body = element('div', 'brand-licence-body');
  const head = element('header', 'brand-licence-head');
  const issuer = element('div', 'brand-licence-issuer');
  issuer.append(svgNode(yxMark({variant: 'compact'})));
  const issuerText = element('div', '');
  issuerText.append(element('strong', '', STRINGS.issuer), element('span', 'brand-caption', STRINGS.issuerCaption));
  issuer.append(issuerText);
  const number = element('div', 'brand-licence-number');
  number.append(element('span', 'brand-caption', STRINGS.fields.serial), element('b', '', model.serial));
  head.append(issuer, number);

  const main = element('div', 'brand-licence-main');
  main.append(element('p', 'brand-licence-heading', STRINGS.heading));
  main.append(element('p', 'brand-caption', STRINGS.headingCaption));
  main.append(element('h3', 'brand-licence-grade', model.title));
  const gradeLine = element('p', 'brand-caption brand-licence-grade-caption');
  gradeLine.textContent = `${STRINGS.gradeCaption} ${model.index} / ${model.count} · ${model.caption}`;
  main.append(gradeLine, ladder(model));

  const figure = element('div', 'brand-licence-figure', model.index);
  figure.setAttribute('aria-hidden', 'true');

  const fields = element('div', 'brand-licence-fields');
  fields.append(
    field(STRINGS.fields.holder, model.holder),
    field(STRINGS.fields.issued, model.issued),
    field(STRINGS.fields.hoursReal, model.hoursReal, STRINGS.hoursUnit),
    field(STRINGS.fields.hoursAssisted, model.hoursAssisted, STRINGS.hoursUnit),
  );
  body.append(head, figure, main, fields);
  card.append(stub, body);
  for (const corner of ['tl', 'tr', 'bl', 'br']) card.append(registration(corner));
  return card;
}
