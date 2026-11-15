// YX licence certificate (viewer/brand/licence_card.js): five grades, index numbers, date and hour formatting
// without a DOM; the licence and component-sheet texts name no vendor.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import {LICENCE_GRADES, STRINGS, licenceModel} from '../viewer/brand/licence_card.js';

const VIEWER = new URL('../viewer/', import.meta.url);
const VENDOR = /\bX1\b|BlueROV|Falcon|Korean Castle|QYSEA|FIFISH|Saab|Seaeye/i;

test('licence texts: five grades, index numbers, dates and hours', function () {
  assert.deepEqual([...LICENCE_GRADES], ['trainee', 'grade2', 'grade1', 'senior', 'supervisor']);
  assert.deepEqual(LICENCE_GRADES.map(function short(id) {
    return STRINGS.grades[id].short;
  }), ['見習', '二級', '一級', '資深', '主管']);
  const model = licenceModel({
    grade: 'grade2', holderName: ' 林見習 ', issuedOn: '2027-02-03T00:00:00Z', hoursReal: 41.25, hoursAssisted: 6,
    serial: 'YX-PL-00417',
  });
  assert.equal(model.index, '02');
  assert.equal(model.count, '05');
  assert.equal(model.title, '二級駕駛員');
  assert.equal(model.holder, '林見習');
  assert.equal(model.issued, '2027.02.03');
  assert.equal(model.hoursReal, '41.3');
  assert.equal(model.hoursAssisted, '6.0');
  const empty = licenceModel({grade: 'admiral'});
  assert.equal(empty.grade, 'trainee');
  assert.equal(empty.holder, STRINGS.empty);
  assert.equal(empty.issued, STRINGS.empty);
  assert.equal(empty.hoursReal, STRINGS.empty);
  assert.equal(licenceModel({hoursReal: -3}).hoursReal, STRINGS.empty);
  assert.equal(licenceModel({issuedOn: new Date(Date.UTC(2026, 10, 15))}).issued, '2026.11.15');
});

test('licence and component sheet texts name no vendor', async function () {
  assert.doesNotMatch(JSON.stringify(STRINGS), VENDOR);
  for (const file of ['demo.js', 'demo_page.js', 'menu_brand.js']) {
    const source = await readFile(new URL(`brand/${file}`, VIEWER), 'utf8');
    const start = source.indexOf('export const STRINGS');
    assert.ok(start >= 0, file);
    assert.doesNotMatch(source.slice(start, source.indexOf('\n};', start)), VENDOR, file);
  }
});
