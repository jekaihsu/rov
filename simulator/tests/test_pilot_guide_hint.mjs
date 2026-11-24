// Pilot-guide context lines come from localize templates, filled with the player's bound keys.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { registerTranslations, setLanguage } from '../viewer/i18n/core.js';
import { pilotGuideHint } from '../viewer/pilot_guide.js';

const LOCALES = new URL('../viewer/i18n/locales/', import.meta.url);

async function loadPilotGuide(locale) {
  const raw = await readFile(new URL(`${locale}/pilot_guide.json`, LOCALES), 'utf8');
  registerTranslations(locale, 'pilot_guide', JSON.parse(raw));
}

test('locked hint uses the bound lock key from the template', async () => {
  await loadPilotGuide('en');
  setLanguage('en');
  const text = pilotGuideHint({
    state: { locked: true },
    progress: {},
    keys: { lock: 'KeyT' },
  });
  assert.match(text, /KeyT/);
  assert.doesNotMatch(text, /\{lock\}/);
});

test('move hint fills the drive caption', async () => {
  setLanguage('zh-Hant');
  const text = pilotGuideHint({
    state: { locked: false },
    progress: { unlock: true, move: false },
    keys: { drive: 'W / S' },
  });
  assert.match(text, /W \/ S/);
  assert.match(text, /緩慢前後移動/);
});

test('English locale swaps the waiting line', async () => {
  await loadPilotGuide('en');
  setLanguage('en');
  assert.match(pilotGuideHint({ state: null }), /Waiting for a link/);
  setLanguage('zh-Hant');
});
