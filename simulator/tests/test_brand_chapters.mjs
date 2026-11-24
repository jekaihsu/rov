// Chapter title card (viewer/brand/chapters.js, chapter_card.js): the table covers every campaign chapter, unknown
// chapters get the generic card, and the card shows only before the dive in the real preset and never in replays.
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {readdir, readFile} from 'node:fs/promises';
import {test} from 'node:test';
import {
  CHAPTER_CARDS, STRINGS, cardTitle, chapterCardData, hasChapterCard, plateFor,
} from '../viewer/brand/chapters.js';
import {
  BOOT_WINDOW_MS, IN_DIVE_ITEM, installChapterCards, shouldShowChapterCard,
} from '../viewer/brand/chapter_card.js';
import {CHAPTER_SYMBOL_IDS} from '../viewer/brand/marks.js';
import {createFidelity, fidelityItems} from '../viewer/fidelity.js';

const VIEWER = new URL('../viewer/', import.meta.url);
const CAMPAIGN = new URL('../campaign/', import.meta.url);
const VENDOR = /\bX1\b|BlueROV|Falcon|Korean Castle|QYSEA|FIFISH|Saab|Seaeye/i;

async function campaignScripts() {
  const names = (await readdir(CAMPAIGN)).filter(function script(name) {
    return name.endsWith('.json') && name !== 'schema.json';
  });
  return Promise.all(names.map(async function load(name) {
    return JSON.parse(await readFile(new URL(name, CAMPAIGN), 'utf8'));
  }));
}

test('the chapter card table covers every campaign chapter', async function () {
  const scripts = await campaignScripts();
  assert.ok(scripts.length >= 20);
  for (const script of scripts) {
    assert.ok(hasChapterCard(script.id), `no card row for ${script.id}`);
    const row = CHAPTER_CARDS[script.id];
    assert.ok(CHAPTER_SYMBOL_IDS.includes(row.symbol), script.id);
    assert.notEqual(row.symbol, 'generic', script.id);
    assert.equal(row.scenario, script.scenario, `${script.id} plate scenario`);
    for (const key of ['number', 'client', 'sub']) assert.ok(row[key], `${script.id}.${key}`);
    const plate = new URL(`brand/plates/${plateFor(row.scenario)}.jpg`, VIEWER);
    assert.ok(existsSync(plate), `plate for ${script.id}: ${plate.pathname}`);
    const data = chapterCardData(script);
    assert.equal(data.title, cardTitle(script.title));
    assert.ok(!data.title.includes('｜'));
  }
  assert.deepEqual(Object.keys(CHAPTER_CARDS).sort(), scripts.map(function id(script) {
    return script.id;
  }).sort(), 'no rows for chapters that do not exist');
});

test('unknown chapters get the generic card', function () {
  const data = chapterCardData({id: 'contract_77', title: '委託｜箱網巡檢'});
  assert.equal(data.symbol, 'generic');
  assert.equal(data.number, '委託');
  assert.equal(data.title, '箱網巡檢');
  assert.equal(data.client, STRINGS.generic.client);
  assert.equal(chapterCardData({id: 'x'}).title, 'x');
  assert.equal(chapterCardData(null).symbol, 'generic');
});

test('the card never shows in a replay and only before the dive in the real preset', function () {
  assert.equal(shouldShowChapterCard({replay: true, bootOpen: true, inDive: true}), false);
  assert.equal(shouldShowChapterCard({replay: false, bootOpen: true, inDive: false}), true);
  assert.equal(shouldShowChapterCard({replay: false, bootOpen: false, inDive: false}), false);
  assert.equal(shouldShowChapterCard({replay: false, bootOpen: false, inDive: true}), true);
  const item = fidelityItems().find(function inDive(entry) {
    return entry.id === IN_DIVE_ITEM;
  });
  assert.equal(item.defaults.real, false);
  assert.equal(item.exceedsReal, true);
});

function campaignState(chapter, status = 'active') {
  const chapters = [{id: 'prologue', title: '序章｜見習之前'}, {id: 'harbor', title: '第一章｜港灣'}];
  return {campaign: {status, chapter, chapters}};
}

test('in-game wiring: one card at start-up, later chapters only with the fidelity item', function () {
  let clock = 0;
  const shown = [];
  function show(data) {
    shown.push(data.id);
  }
  function now() {
    return clock;
  }
  const real = createFidelity({search: '?fidelity=real'});
  const cards = installChapterCards({fidelity: real, now, show});
  cards.update(campaignState('', 'idle'));
  clock = 1500;
  cards.update(campaignState('prologue'));
  cards.update(campaignState('prologue'));
  assert.deepEqual(shown, ['prologue']);
  clock = 400000;
  cards.update(campaignState('prologue', 'completed'));
  cards.update(campaignState('harbor'));
  assert.deepEqual(shown, ['prologue'], 'real: no card over the camera view mid-dive');
  real.set(IN_DIVE_ITEM, true);
  cards.update(campaignState('harbor', 'completed'));
  cards.update(campaignState('harbor'));
  assert.deepEqual(shown, ['prologue', 'harbor']);

  const late = [];
  clock = 0;
  const lateCards = installChapterCards({
    fidelity: createFidelity({search: '?fidelity=real'}),
    now,
    show(data) {
      late.push(data.id);
    },
  });
  lateCards.update(campaignState('', 'idle'));
  clock = BOOT_WINDOW_MS + 1;
  lateCards.update(campaignState('prologue'));
  assert.deepEqual(late, [], 'a chapter started after start-up is mid-dive');

  const replay = [];
  const replayCards = installChapterCards({
    readOnly: true,
    fidelity: createFidelity({search: '?fidelity=assisted'}),
    now,
    show(data) {
      replay.push(data.id);
    },
  });
  replayCards.update(campaignState('prologue'));
  assert.deepEqual(replay, []);
});

test('card texts name no vendor', function () {
  assert.doesNotMatch(JSON.stringify(STRINGS), VENDOR);
});
