// Entry of brand/demo.html. Without a query it shows the whole component sheet; ?card=<chapter id> fills the page
// with that chapter's title card and ?licence=<grade id> with one licence on the main colour, which is how the
// screenshots in docs/design/key-art/in-game/ are taken.
import {CHAPTER_CARDS, chapterCardData} from './chapters.js';
import {titleCard} from './chapter_card.js';
import {buildBrandDemo} from './demo.js';
import {LICENCE_GRADES, licenceCard} from './licence_card.js';
import { localize } from '../i18n/index.js';

export const STRINGS = localize('brand.demo_page', {
  titles: {
    prologue: '序章｜水池',
    harbor: '第一章｜港灣',
    hull: '第一章｜船殼',
    offshore: '第二章｜離岸',
    reef: '第三章｜礁區',
    wreck: '第四章｜沉船',
    finale: '終章｜夜間回收',
  },
  holder: '林見習',
});

const SAMPLE_LICENCE = {
  trainee: {issuedOn: Date.UTC(2026, 10, 15), hoursReal: 3.5, hoursAssisted: 1.5, serial: 'YX-PL-00417'},
  grade2: {issuedOn: Date.UTC(2027, 1, 3), hoursReal: 41.2, hoursAssisted: 6, serial: 'YX-PL-00417'},
  grade1: {issuedOn: Date.UTC(2027, 7, 21), hoursReal: 186.4, hoursAssisted: 12.5, serial: 'YX-PL-00417'},
  senior: {issuedOn: Date.UTC(2028, 4, 9), hoursReal: 512, hoursAssisted: 20, serial: 'YX-PL-00417'},
  supervisor: {issuedOn: Date.UTC(2029, 2, 30), hoursReal: 1204.8, hoursAssisted: 31.2, serial: 'YX-PL-00417'},
};

function showCard(id) {
  const stage = document.createElement('div');
  stage.className = 'brand-card-overlay brand-card-static';
  const title = STRINGS.titles[id] || id;
  stage.append(titleCard(chapterCardData({id, title, scenario: CHAPTER_CARDS[id]?.scenario})));
  document.body.append(stage);
}

function showLicence(grade) {
  const stage = document.createElement('div');
  stage.className = 'brand-licence-stage';
  const id = LICENCE_GRADES.includes(grade) ? grade : LICENCE_GRADES[0];
  stage.append(licenceCard({grade: id, holderName: STRINGS.holder, ...SAMPLE_LICENCE[id]}));
  document.body.append(stage);
}

function start() {
  const query = new URLSearchParams(location.search);
  if (query.has('card')) showCard(query.get('card'));
  else if (query.has('licence')) showLicence(query.get('licence'));
  else document.body.append(buildBrandDemo());
  document.documentElement.dataset.ready = '1';
}

start();
