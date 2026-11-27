// Cold open: the beat director (story/cold_open_model.js) and the new-game rule (story/cold_open_flow.js).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import { TIMING, createColdOpenDirector } from '../viewer/story/cold_open_model.js';
import {
  CHAPTER, FLAG, NEXT, SCENARIO, STORAGE_KEY, coldOpenUrl, followUpUrl, isNewGame, loadColdOpen, markColdOpenSeen,
  playsBefore, setColdOpenEnabled, startsPrologue,
} from '../viewer/story/cold_open_flow.js';

const SPOTS = {anode: [-6.93, -6.93], start: [-12, -9]};
const AT_START = {photos: 0, snagged: false, tension: 1, pos: [-12, -9, 12], input: 0};

// Steps the director at 10 Hz from `from` to `to` seconds with a telemetry function of time; collects every view.
function run(director, from, to, telemetry) {
  const views = [];
  for (let t = from; t <= to + 1e-9; t += 0.1) views.push(director.step(Math.round(t * 10) / 10, telemetry(t)));
  return views;
}

function said(views) {
  return views.flatMap(function lines(view) {
    return view.said.map(function id(entry) {
      return entry.id;
    });
  });
}

function beats(views) {
  return [...new Set(views.map(function beat(view) {
    return view.beat;
  }))];
}

function memoryStorage() {
  const data = new Map();
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
  };
}

test('a full run: photo, snag, back out, card', () => {
  const director = createColdOpenDirector(SPOTS);
  const opening = run(director, 0, 15, () => AT_START);
  assert.deepEqual(beats(opening), ['black', 'establish', 'handover', 'approach']);
  assert.equal(opening[0].black, 1);
  assert.ok(opening[0].letterbox && opening[0].cinematic);
  assert.deepEqual(said(opening), ['open', 'crew', 'task']);
  const approach = opening.at(-1);
  assert.equal(approach.hint, 'move');
  assert.deepEqual(approach.reveal.sort(), ['depth', 'heading']);
  assert.equal(approach.black, 0);
  assert.ok(!approach.letterbox);
  // Near the anode the hint becomes the shutter; the photo pays off with praise.
  const near = {...AT_START, pos: [-7.5, -7.5, 12], input: 0.5};
  assert.equal(director.step(20, near).hint, 'photo');
  const payoff = director.step(21, {...near, photos: 1});
  assert.equal(payoff.beat, 'payoff');
  assert.deepEqual(payoff.said.map((entry) => entry.id), ['praise']);
  assert.ok(payoff.reveal.includes('photo'));
  const transit = run(director, 21.1, 28, () => ({...near, photos: 1, input: 0.6}));
  assert.equal(transit.at(-1).beat, 'transit');
  assert.equal(transit.at(-1).hint, 'turn');
  assert.ok(said(transit).includes('toLegB'));
  assert.equal(director.step(28.01, {...near, heading: 350}).hint, 'forward');
  assert.equal(director.step(28.02, {...near, heading: 80}).hint, 'turn');
  // A hook that lets go at once is not the incident; one that holds is.
  assert.equal(director.step(28.1, {...near, photos: 1, snagged: true, tension: 30}).beat, 'transit');
  assert.equal(director.step(28.2, {...near, photos: 1, snagged: false}).beat, 'transit');
  const caught = run(director, 28.3, 29.5, () => ({...near, photos: 1, snagged: true, tension: 54}));
  assert.equal(caught.at(-1).beat, 'incident');
  const call = caught.flatMap((view) => view.said).find((entry) => entry.id === 'tension');
  assert.deepEqual(call.params, {n: 50});
  assert.ok(said(caught).includes('stop'));
  assert.ok(caught.at(-1).reveal.includes('tether'));
  assert.equal(caught.at(-1).hint, 'release');
  // The pilot stops pulling: the back-out call and the reverse hint.
  const stopped = run(director, 29.6, 32, () => ({...near, photos: 1, snagged: true, tension: 4}));
  assert.ok(said(stopped).includes('backOut'));
  assert.equal(stopped.at(-1).hint, 'reverse');
  // Pulling again draws the tender's call; a short release flicker does not end it.
  const pulled = run(director, 32.1, 40, () => ({...near, photos: 1, snagged: true, tension: 60}));
  assert.ok(said(pulled).includes('dontPull'));
  assert.equal(director.step(40.1, {...near, photos: 1, snagged: false}).beat, 'incident');
  const free = run(director, 40.2, 42, () => ({...near, photos: 1, snagged: false, tension: 2}));
  assert.equal(free.at(-1).beat, 'relief');
  assert.deepEqual(said(free), ['free', 'remember']);
  const closing = run(director, 42.1, 42 + TIMING.relief + TIMING.fade + 0.5, () => ({...near, photos: 1}));
  assert.deepEqual(beats(closing), ['relief', 'fade', 'card']);
  assert.ok(closing.at(-1).ended);
  assert.equal(closing.at(-1).black, 1);
  assert.deepEqual(closing.at(-1).outcome, {photo: true, snag: true, released: true, broken: false, skipped: false});
});

test('an idle player is prompted and the story still moves on', () => {
  const director = createColdOpenDirector(SPOTS);
  run(director, 0, 15, () => AT_START);
  const waiting = run(director, 15.1, 15 + TIMING.approachLimit + 1, () => AT_START);
  const lines = said(waiting);
  assert.ok(lines.includes('nudgeMove'), lines);
  assert.ok(lines.includes('nudgePhoto'), lines);
  assert.equal(waiting.at(-1).beat, 'transit');
  assert.ok(lines.includes('skipPhoto'));
  const from = 15 + TIMING.approachLimit + 1.1;
  const transit = run(director, from, from + TIMING.transitLimit + 1, () => AT_START);
  assert.ok(said(transit).includes('nudgeLegB'));
  assert.equal(transit.at(-1).beat, 'relief');
  assert.ok(said(transit).includes('noSnag'));
  const end = from + TIMING.transitLimit + 1.1;
  const closing = run(director, end, end + TIMING.relief + TIMING.fade + 0.5, () => AT_START);
  assert.ok(closing.at(-1).ended);
  assert.deepEqual(closing.at(-1).outcome, {photo: false, snag: false, released: false, broken: false, skipped: false});
});

test('a snag that is never cleared still ends the scene', () => {
  const director = createColdOpenDirector(SPOTS);
  run(director, 0, 15, () => AT_START);
  director.step(16, {...AT_START, photos: 1});
  run(director, 16.1, 23, () => ({...AT_START, photos: 1}));
  const stuck = run(director, 23.1, 23 + TIMING.incidentLimit + 2, () => ({...AT_START, photos: 1, snagged: true,
    tension: 50}));
  assert.ok(said(stuck).includes('stuck'));
  assert.equal(stuck.at(-1).beat, 'relief');
  assert.ok(stuck.at(-1).outcome.snag && !stuck.at(-1).outcome.released);
});

test('a snag that lets go before the back-out call is luck, not a recovery', () => {
  const director = createColdOpenDirector(SPOTS);
  run(director, 0, 15, () => AT_START);
  director.step(16, {...AT_START, photos: 1});
  run(director, 16.1, 23, () => ({...AT_START, photos: 1}));
  // A hook shorter than the confirmation time is not the incident.
  const brief = run(director, 23.1, 23 + TIMING.snagConfirm - 0.2, () => ({...AT_START, photos: 1, snagged: true,
    tension: 30}));
  assert.equal(brief.at(-1).beat, 'transit');
  run(director, 24, 25, () => ({...AT_START, photos: 1}));
  const caught = run(director, 25.1, 26.5, () => ({...AT_START, photos: 1, snagged: true, tension: 55}));
  assert.equal(caught.at(-1).beat, 'incident');
  assert.ok(!said(caught).includes('backOut'));
  // Still pulling, the hook slides off by itself: the story goes on, and nobody calls it a clean recovery.
  const slipped = run(director, 26.6, 26.6 + TIMING.releaseConfirm + 0.3, () => ({...AT_START, photos: 1,
    snagged: false, tension: 30}));
  assert.equal(slipped.at(-1).beat, 'relief');
  assert.deepEqual(said(slipped), ['slipped', 'lucky']);
  assert.ok(slipped.at(-1).outcome.snag && slipped.at(-1).outcome.released);
  const end = 26.6 + TIMING.releaseConfirm + 0.4;
  const closing = run(director, end, end + TIMING.relief + TIMING.fade + 0.5, () => ({...AT_START, photos: 1}));
  assert.ok(closing.at(-1).ended);
});

test('a tether pulled apart ends the scene without calling it free', () => {
  const director = createColdOpenDirector(SPOTS);
  run(director, 0, 15, () => AT_START);
  director.step(16, {...AT_START, photos: 1});
  run(director, 16.1, 23, () => ({...AT_START, photos: 1}));
  run(director, 23.1, 24, () => ({...AT_START, photos: 1, snagged: true, tension: 300}));
  // The snag list empties when the tether parts; that is not a release.
  const parted = run(director, 24.1, 27, () => ({...AT_START, photos: 1, snagged: false, broken: true}));
  assert.equal(parted.at(-1).beat, 'relief');
  const lines = said(parted);
  assert.ok(lines.includes('snapped') && lines.includes('lost'), lines);
  assert.ok(!lines.includes('free'));
  assert.deepEqual(parted.at(-1).outcome, {photo: true, snag: true, released: false, broken: true, skipped: false});
});

test('a replay can skip to the card', () => {
  const director = createColdOpenDirector(SPOTS);
  director.step(0, AT_START);
  const view = director.skip(3);
  assert.equal(view.beat, 'card');
  assert.ok(view.ended && view.outcome.skipped);
  assert.equal(view.hint, null);
});

test('only a new game or a first prologue plays it, once, unless turned off', () => {
  globalThis.localStorage = memoryStorage();
  const prologue = {mission: 'campaign', chapter: 'prologue'};
  assert.deepEqual(loadColdOpen(), {seen: false, enabled: true});
  assert.ok(startsPrologue(prologue));
  assert.ok(!startsPrologue({mission: 'campaign', chapter: 'harbor'}));
  assert.ok(!startsPrologue({...prologue, multiplayer: true}));
  assert.ok(playsBefore(prologue));
  assert.ok(!playsBefore({mission: 'free_explore', chapter: ''}));
  assert.ok(isNewGame({}));
  assert.ok(isNewGame({career: {money: 0, logbook: []}}));
  assert.ok(!isNewGame({hasLastSession: true}));
  assert.ok(!isNewGame({career: {money: 4000, logbook: [{}]}}));
  assert.ok(!isNewGame({completedChapters: ['prologue']}));
  setColdOpenEnabled(false);
  assert.ok(!playsBefore(prologue) && !isNewGame({}));
  setColdOpenEnabled(true);
  markColdOpenSeen();
  assert.deepEqual(JSON.parse(localStorage.getItem(STORAGE_KEY)), {seen: true, enabled: true});
  assert.ok(!playsBefore(prologue) && !isNewGame({}));
  delete globalThis.localStorage;
});

test('the cold-open URL carries the follow-up launch and comes back to it', () => {
  const launch = 'http://127.0.0.1:8080/?play=1&ws=ws%3A%2F%2F127.0.0.1%3A8765&scenario=tutorial_pool&mission=campaign'
    + '&chapter=prologue&contract=p0_induction&room=training';
  const url = coldOpenUrl(launch);
  assert.equal(url.searchParams.get('chapter'), CHAPTER);
  assert.equal(url.searchParams.get('scenario'), SCENARIO);
  assert.equal(url.searchParams.get(FLAG), '1');
  assert.equal(url.searchParams.get('nointro'), '1');
  assert.equal(url.searchParams.get('contract'), null, 'the cold open is not the work order');
  assert.equal(url.searchParams.get('ws'), 'ws://127.0.0.1:8765');
  assert.equal(url.searchParams.get('room'), 'training-cold', 'its own room, so the prologue starts idle');
  const back = new URL(followUpUrl(url.href));
  assert.equal(back.searchParams.get('contract'), 'p0_induction');
  assert.equal(back.searchParams.get('chapter'), 'prologue');
  assert.equal(back.searchParams.get(FLAG), null);
  assert.equal(back.searchParams.get('room'), 'training');
  const replay = coldOpenUrl(launch, {replay: true});
  assert.equal(replay.searchParams.get(FLAG), 'replay');
  const menu = new URL(followUpUrl(replay.href));
  assert.equal(menu.searchParams.get('menu'), 'training');
  assert.equal(menu.searchParams.get('tab'), 'story');
  assert.equal(menu.searchParams.get('play'), null, 'a replay returns to the launch menu');
  assert.ok(!new URL(followUpUrl('http://x/?play=1')).search.includes(NEXT));
});

test('the cold open is a prelude campaign entry that keeps the prologue untouched', async () => {
  const script = JSON.parse(await readFile(new URL('../campaign/cold_open.json', import.meta.url), 'utf8'));
  assert.equal(script.category, 'prelude');
  assert.equal(script.scenario, SCENARIO);
  assert.equal(script.id, CHAPTER);
  const catalogue = JSON.parse(await readFile(new URL('../viewer/menu_catalogue.json', import.meta.url), 'utf8'));
  const prelude = catalogue.chapters.filter((chapter) => chapter.category === 'prelude');
  assert.deepEqual(prelude.map((chapter) => chapter.id), [CHAPTER]);
  const prologue = JSON.parse(await readFile(new URL('../campaign/prologue.json', import.meta.url), 'utf8'));
  assert.equal(prologue.requires, null, 'the prologue does not require the cold open');
});
