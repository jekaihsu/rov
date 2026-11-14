// Tether reel controls: the autoPayout fidelity item and the reel/legacy message selection.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createFidelity} from '../viewer/fidelity.js';
import {installTetherReel, reelCommandFor} from '../viewer/tether_reel.js';

function fakeDocument() {
  const toggle = {checked: false, onchange: null};
  const buttons = ['haul_in', 'hold', 'free', 'pay_out'].map(function makeButton(command) {
    return {dataset: {reel: command}, onclick: null, classList: {toggle() {}}};
  });
  return {
    activeElement: null,
    toggle,
    buttons,
    getElementById(id) {
      return id === 'autoPay' ? toggle : null;
    },
    querySelectorAll() {
      return buttons;
    }
  };
}

test('auto payout is a fidelity item: off in real, on in assisted', function () {
  const real = createFidelity();
  assert.equal(real.get('autoPayout'), false);
  assert.equal(real.exceeds('autoPayout'), false);
  const assisted = createFidelity({search: '?fidelity=assisted'});
  assert.equal(assisted.get('autoPayout'), true);
  assert.equal(assisted.exceeds('autoPayout'), true);
});

test('real mode leaves the drum free; assisted keeps tension', function () {
  assert.deepEqual(reelCommandFor(false), {type: 'reel', command: 'free'});
  assert.deepEqual(reelCommandFor(true), {type: 'reel', command: 'auto'});
});

test('reel messages only go to servers that report tether.reel', function () {
  const doc = fakeDocument();
  const sent = [];
  const fidelity = createFidelity();
  const update = installTetherReel({send: (msg) => sent.push(msg), doc, fidelity});
  update({length: 30, auto_payout: true}, 5);
  assert.deepEqual(sent.at(-1), {type: 'auto_payout', value: false});
  doc.buttons[0].onclick({currentTarget: doc.buttons[0]});
  assert.deepEqual(sent.at(-1), {type: 'payout', metres: -1});
  update({length: 30, auto_payout: false, reel: {mode: 'hold'}}, 0);  // scenario reset re-applies fidelity
  assert.deepEqual(sent.at(-1), {type: 'reel', command: 'free'});
  doc.buttons[3].onclick({currentTarget: doc.buttons[3]});
  assert.deepEqual(sent.at(-1), {type: 'reel', command: 'pay_out'});
  fidelity.set('autoPayout', true);
  assert.deepEqual(sent.at(-1), {type: 'reel', command: 'auto'});
});
