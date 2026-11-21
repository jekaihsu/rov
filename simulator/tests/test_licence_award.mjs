// Licence award helpers (viewer/brand/licence_award.js): props only when an exam newly grants a grade.
import test from 'node:test';
import assert from 'node:assert/strict';
import {awardProps, licenceSerial} from '../viewer/brand/licence_award.js';

test('licenceSerial is stable for the same save seed', () => {
  const save = {createdAt: '2026-11-17T00:00:00.000Z'};
  assert.equal(licenceSerial(save), licenceSerial(save));
  assert.match(licenceSerial(save), /^YX-PL-\d{5}$/);
});

test('awardProps returns trainee card data only on a new grant', () => {
  const summary = {
    exam: {passed: true, granted: '見習駕駛員'},
    licence: {before: 'none', after: 'trainee'},
    hours: {total_real_s: 7200, total_assisted_s: 600},
  };
  const props = awardProps(summary, {createdAt: '2026-11-17T00:00:00.000Z', updatedAt: '2026-11-17T01:00:00.000Z'});
  assert.equal(props.grade, 'trainee');
  assert.equal(props.hoursReal, 2);
  assert.equal(props.hoursAssisted, 600 / 3600);
  assert.match(props.serial, /^YX-PL-/);
  assert.equal(awardProps({...summary, exam: {passed: false}}, {}), null);
  assert.equal(awardProps({
    exam: {passed: true},
    licence: {before: 'trainee', after: 'trainee'},
    hours: {},
  }, {}), null);
});
