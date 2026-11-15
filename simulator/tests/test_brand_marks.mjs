// YX identity marks (viewer/brand/marks.js): deterministic SVG strings, three or four elements per symbol plus one
// accent, legible strokes from 32 px to 600 px, and no vendor name or internal model id in the markup.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {
  BRAND_COLOURS, CHAPTER_SYMBOL_IDS, FLEET_SYMBOL_IDS, MARK_PATHS, chapterSymbol, chapterSymbolId, fleetLetter,
  fleetSymbol, fleetSymbolId, loadingMark, strokeFor, symbolParts, yxMark,
} from '../viewer/brand/marks.js';
import {FLEET_IDS} from '../viewer/fleet_names.js';

const VENDOR = /\bX1\b|BlueROV|Falcon|Korean Castle|QYSEA|FIFISH|Saab|Seaeye/i;

function count(markup, pattern) {
  return (markup.match(pattern) || []).length;
}

function allMarkup() {
  const marks = [
    yxMark(), yxMark({variant: 'compact'}), yxMark({variant: 'tether', misregister: false}), loadingMark(),
  ];
  const fleet = [...FLEET_SYMBOL_IDS, 'unknown'].map(function draw(id) {
    return fleetSymbol(id, {rough: true});
  });
  const chapters = [...CHAPTER_SYMBOL_IDS, 'unknown'].map(function draw(id) {
    return chapterSymbol(id);
  });
  return [...marks, ...fleet, ...chapters];
}

test('marks are deterministic, well-formed SVG strings', function () {
  const first = allMarkup();
  const second = allMarkup();
  assert.deepEqual(first, second);
  for (const markup of first) {
    assert.match(markup, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="[\d. ]+"/);
    assert.ok(markup.endsWith('</svg>'));
    assert.equal(count(markup, /<svg/g), 1);
    assert.doesNotMatch(markup, /undefined|NaN|null/);
    assert.equal(count(markup, /<(path|circle|rect|g|filter)\b/g) > 0, true);
  }
});

test('no mark names a vendor or an internal model id', function () {
  for (const markup of allMarkup()) {
    assert.doesNotMatch(markup, VENDOR);
    assert.doesNotMatch(markup, /bluerov|falcon|x1/i);
  }
});

test('the YX mark has its two variants', function () {
  const tether = yxMark();
  assert.equal(count(tether, /data-part="tether"/g), 1);
  assert.equal(count(tether, /data-part="misregister"/g), 1);
  assert.equal(count(tether, /data-part="hub"/g), 1);
  assert.ok(tether.includes(MARK_PATHS.tether));
  // The misregistered print is the only accent in the default tether mark.
  assert.equal(count(tether, /class="yx-accent"/g), 1);
  const plain = yxMark({variant: 'tether', misregister: false});
  assert.equal(count(plain, /data-part="misregister"/g), 0);
  assert.equal(count(plain, /class="yx-accent"/g), 1);
  const compact = yxMark({variant: 'compact', ink: '#eef3f0', accent: '#123456'});
  assert.equal(count(compact, /<path/g), 4);
  assert.equal(count(compact, /class="yx-accent"/g), 1, 'accent on one stroke only');
  assert.equal(count(compact, /#123456/g), 1);
  assert.equal(count(compact, /data-part="tether"/g), 0);
  assert.ok(compact.includes('stroke="#eef3f0"'));
  assert.equal(yxMark({variant: 'compact', size: 32, sized: true}).includes('height="32"'), true);
});

test('every fleet model has a symbol of three or four elements plus one accent', function () {
  assert.deepEqual([...FLEET_SYMBOL_IDS], [...FLEET_IDS, 'model_s']);
  assert.deepEqual(FLEET_SYMBOL_IDS.map(fleetLetter), ['R', 'O', 'V', 'S']);
  for (const id of FLEET_SYMBOL_IDS) {
    const parts = symbolParts('fleet', id);
    assert.ok(parts.length >= 3 && parts.length <= 4, `${id}: ${parts}`);
    const markup = fleetSymbol(id);
    for (const name of parts) assert.equal(count(markup, new RegExp(`data-part="${name}"`, 'g')), 1, name);
    assert.equal(count(markup, /data-part="accent"/g), 1);
    assert.ok(markup.includes(BRAND_COLOURS.accent));
  }
  assert.equal(fleetSymbolId('something_new'), 'model_s');
  assert.equal(fleetSymbol('something_new'), fleetSymbol('model_s'));
});

test('the work models read as vehicles: float block, open frame, arm with a jaw, tether or lift point', function () {
  assert.deepEqual(symbolParts('fleet', 'falcon'), ['float', 'frame', 'arm', 'tether']);
  assert.deepEqual(symbolParts('fleet', 'model_s'), ['float', 'frame', 'arms', 'lift']);
  // The float is a solid block, not an outlined screen.
  assert.match(fleetSymbol('falcon'), /<rect data-part="float"[^>]*fill="currentColor" stroke="none"/);
  assert.match(fleetSymbol('model_s'), /<rect data-part="float"[^>]*fill="currentColor" stroke="none"/);
});

test('chapter symbols have three elements plus one accent and fall back to generic', function () {
  for (const id of CHAPTER_SYMBOL_IDS) {
    const parts = symbolParts('chapter', id);
    assert.equal(parts.length, 3, id);
    assert.equal(count(chapterSymbol(id), /data-part="accent"/g), 1, id);
  }
  assert.equal(chapterSymbolId('nowhere'), 'generic');
  assert.equal(chapterSymbol('nowhere'), chapterSymbol('generic'));
});

test('the stroke follows the display size so symbols hold at 32 px and at 600 px', function () {
  const small = strokeFor(32);
  const large = strokeFor(600);
  // Width on screen = box units * size / 120.
  assert.ok(small.main * 32 / 120 >= 1.5, 'main line at least 1.5 px at 32 px');
  assert.ok(small.fine * 32 / 120 >= 1, 'fine line at least 1 px at 32 px');
  assert.ok(large.main * 600 / 120 <= 6, 'main line stays thin at 600 px');
  assert.ok(large.main < small.main);
  assert.notEqual(fleetSymbol('x1', {size: 32}), fleetSymbol('x1', {size: 600}));
});
