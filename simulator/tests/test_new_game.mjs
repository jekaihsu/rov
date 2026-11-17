// New-game difficulty screen: persistence flag and preset wiring stay in sync with fidelity.js.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createFidelity} from '../viewer/fidelity.js';
import {
  DIFFICULTY_CHOSEN_KEY, hasDifficultyChosen, rememberDifficultyChosen, difficultyLabel,
} from '../viewer/menu/new_game.js';
import '../viewer/start_presentation.js';
import '../viewer/procedure/fidelity_item.js';

function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return data.has(key) ? data.get(key) : null;
    },
    setItem(key, value) {
      data.set(key, String(value));
    },
    data,
  };
}

test('difficulty chosen flag starts false and sticks after remember', function () {
  const storage = memoryStorage();
  assert.equal(hasDifficultyChosen(storage), false);
  rememberDifficultyChosen(storage);
  assert.equal(hasDifficultyChosen(storage), true);
  assert.equal(storage.data.get(DIFFICULTY_CHOSEN_KEY), '1');
});

test('difficulty labels match the player-facing preset names', function () {
  assert.equal(difficultyLabel('assisted'), '簡單');
  assert.equal(difficultyLabel('standard'), '標準');
  assert.equal(difficultyLabel('real'), '真實');
});

test('standard preset arms depth hold and near start without station keeping', function () {
  const fidelity = createFidelity({search: '?fidelity=standard'});
  assert.equal(fidelity.preset, 'standard');
  assert.equal(fidelity.get('assistLevel'), 0);
  assert.equal(fidelity.get('videoDelayMs'), 150);
  assert.equal(fidelity.get('depthHoldStart'), true);
  assert.equal(fidelity.get('nearStart'), true);
  assert.equal(fidelity.get('thirdPerson'), false);
});

test('all difficulty presets keep the full deck procedure (simple uses crew via beginFields)', function () {
  for (const name of ['assisted', 'standard', 'real']) {
    const fidelity = createFidelity({search: `?fidelity=${name}`});
    assert.equal(fidelity.get('deployProcedure'), 'full', name);
  }
});
