// Component sheet of the YX identity: the mark, fleet and chapter symbols, chapter title cards and the licence
// certificate in every grade. brand/demo.html shows it on its own; the launch menu opens the same sheet with
// ?brandDemo. Sample values only; nothing here reads a save.
import {CHAPTER_CARDS, chapterCardData} from './chapters.js';
import {showTitleCard, titleCard} from './chapter_card.js';
import {LICENCE_GRADES, licenceCard} from './licence_card.js';
import {
  BRAND_COLOURS, CHAPTER_SYMBOL_IDS, FLEET_SYMBOL_IDS, chapterSymbol, fleetLetter, fleetSymbol, svgNode, yxMark,
} from './marks.js';

export import { localize } from '../i18n/index.js';

const STRINGS = localize('brand.demo', {
  title: 'YX 識別元件',
  caption: 'YX — IDENTITY COMPONENTS',
  sections: {
    mark: ['01', '標誌', 'MARK'],
    fleet: ['02', '機隊符號', 'FLEET SYMBOLS'],
    chapters: ['03', '章節符號', 'CHAPTER SYMBOLS'],
    cards: ['04', '章節標題卡', 'CHAPTER TITLE CARDS'],
    licence: ['05', '操作員執照', 'PILOT LICENCE'],
  },
  model: 'MODEL',
  play: '全螢幕播放',
  sampleTitles: {prologue: '序章｜水池', harbor: '第一章｜港灣', offshore: '第二章｜離岸'},
  sampleHolder: '林見習',
  sampleSerialPrefix: 'YX-PL-',
});

const SAMPLE_CARDS = ['prologue', 'harbor', 'offshore'];
const SAMPLE_HOURS = {
  trainee: [3.5, 1.5],
  grade2: [41.2, 6.0],
  grade1: [186.4, 12.5],
  senior: [512.0, 20.0],
  supervisor: [1204.8, 31.2],
};
const SYMBOL_SIZES = [96, 48, 32];

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function section(key) {
  const [index, title, caption] = STRINGS.sections[key];
  const root = element('section', 'brand-demo-section');
  root.dataset.section = key;
  const head = element('header', 'brand-demo-head');
  head.append(element('span', 'brand-demo-index', index), element('h2', '', title));
  head.append(element('span', 'brand-caption', caption));
  root.append(head);
  return root;
}

function markSection() {
  const root = section('mark');
  const row = element('div', 'brand-demo-row');
  const light = element('div', 'brand-demo-swatch');
  light.append(svgNode(yxMark({variant: 'tether', paper: BRAND_COLOURS.paper})));
  const dark = element('div', 'brand-demo-swatch brand-demo-swatch-dark');
  dark.append(svgNode(yxMark({variant: 'compact'})));
  row.append(light, dark);
  root.append(row);
  return root;
}

function symbolTile(caption, draw) {
  const tile = element('figure', 'brand-demo-tile');
  const sizes = element('div', 'brand-demo-sizes');
  for (const size of SYMBOL_SIZES) sizes.append(svgNode(draw({size, sized: true})));
  tile.append(sizes, element('figcaption', 'brand-caption', caption));
  return tile;
}

function fleetSection() {
  const root = section('fleet');
  const row = element('div', 'brand-demo-row');
  for (const id of FLEET_SYMBOL_IDS) {
    row.append(symbolTile(`${STRINGS.model} ${fleetLetter(id)}`, function drawFleet(options) {
      return fleetSymbol(id, options);
    }));
  }
  root.append(row);
  return root;
}

function chapterSection() {
  const root = section('chapters');
  const row = element('div', 'brand-demo-row');
  for (const id of CHAPTER_SYMBOL_IDS) {
    row.append(symbolTile(id.toUpperCase(), function drawChapter(options) {
      return chapterSymbol(id, options);
    }));
  }
  root.append(row);
  return root;
}

function sampleCard(id) {
  return chapterCardData({id, title: STRINGS.sampleTitles[id], scenario: CHAPTER_CARDS[id].scenario});
}

function cardSection() {
  const root = section('cards');
  const row = element('div', 'brand-demo-cards');
  for (const id of SAMPLE_CARDS) {
    const frame = element('div', 'brand-demo-card');
    frame.dataset.card = id;
    const play = element('button', 'brand-demo-play brand-caption', STRINGS.play);
    play.type = 'button';
    play.addEventListener('click', function playCard() {
      showTitleCard(sampleCard(id));
    });
    frame.append(titleCard(sampleCard(id)), play);
    row.append(frame);
  }
  root.append(row);
  return root;
}

function licenceSection() {
  const root = section('licence');
  const row = element('div', 'brand-demo-licences');
  LICENCE_GRADES.forEach(function addLicence(grade, index) {
    const [hoursReal, hoursAssisted] = SAMPLE_HOURS[grade];
    row.append(licenceCard({
      grade,
      holderName: STRINGS.sampleHolder,
      issuedOn: Date.UTC(2026, 10, 15 + index),
      hoursReal,
      hoursAssisted,
      serial: `${STRINGS.sampleSerialPrefix}${String(417 + index * 36).padStart(5, '0')}`,
    }));
  });
  root.append(row);
  return root;
}

/** The whole component sheet as one element. */
export function buildBrandDemo() {
  const root = element('div', 'brand-demo brand-paper');
  const head = element('header', 'brand-demo-title');
  head.append(element('h1', '', STRINGS.title), element('span', 'brand-caption', STRINGS.caption));
  root.append(head, markSection(), fleetSection(), chapterSection(), cardSection(), licenceSection());
  return root;
}
